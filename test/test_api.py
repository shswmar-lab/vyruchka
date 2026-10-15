"""API-тесты «Выручка водителей» (FastAPI + SQLite).

Запуск: pytest -q
"""


def login(client, username: str, password: str):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def make_user(client, username="ivan", password="password1", role="user"):
    """Создать пользователя от имени админа и вернуть его id."""
    r = login(client, "admin", "adminpass123")
    assert r.status_code == 200
    r2 = client.post(
        "/api/users",
        json={"username": username, "password": password, "role": role, "full_name": "Иван"},
    )
    assert r2.status_code == 201, r2.text
    return r2.json()["id"]


# ── Аутентификация ──────────────────────────────────────────
def test_login_success_and_me(api_client):
    r = login(api_client, "admin", "adminpass123")
    assert r.status_code == 200
    me = api_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "admin"
    assert me.json()["role"] == "admin"


def test_login_wrong_password(api_client):
    assert login(api_client, "admin", "wrong").status_code == 401


def test_login_unknown_user(api_client):
    assert login(api_client, "nobody", "password1").status_code == 401


def test_auth_public_users(api_client):
    make_user(api_client, "ivan", "password1", role="user")
    login(api_client, "admin", "adminpass123")
    r = api_client.post(
        "/api/users",
        json={
            "username": "blocked",
            "password": "password1",
            "role": "user",
            "full_name": "Блок",
            "is_active": False,
        },
    )
    assert r.status_code == 201, r.text
    api_client.post("/api/auth/logout")
    users = api_client.get("/api/auth/users")
    assert users.status_code == 200
    names = [u["username"] for u in users.json()]
    assert "admin" in names and "ivan" in names
    assert "blocked" not in names


def test_me_unauthorized(api_client):
    assert api_client.get("/api/auth/me").status_code == 401


def test_logout_clears_session(api_client):
    login(api_client, "admin", "adminpass123")
    assert api_client.post("/api/auth/logout").status_code == 200
    assert api_client.get("/api/auth/me").status_code == 401


def test_blocked_user_cannot_login(api_client):
    uid = make_user(api_client, "ivan", "password1")
    login(api_client, "admin", "adminpass123")
    api_client.put(f"/api/users/{uid}", json={"is_active": False})
    assert login(api_client, "ivan", "password1").status_code == 403


# ── Пользователи (админ) ────────────────────────────────────
def test_users_admin_crud(api_client):
    uid = make_user(api_client, "petr", "password1", role="user")
    lst = api_client.get("/api/users")
    assert lst.status_code == 200
    assert {"admin", "petr"} <= {u["username"] for u in lst.json()}

    upd = api_client.put(f"/api/users/{uid}", json={"role": "admin", "full_name": "Пётр П."})
    assert upd.status_code == 200
    assert upd.json()["role"] == "admin"
    assert upd.json()["full_name"] == "Пётр П."

    assert api_client.delete(f"/api/users/{uid}").status_code == 200
    remaining = {u["username"] for u in api_client.get("/api/users").json()}
    assert "petr" not in remaining


def test_users_non_admin_forbidden(api_client):
    make_user(api_client, "ivan", "password1", role="user")
    login(api_client, "ivan", "password1")
    assert api_client.get("/api/users").status_code == 403
    assert api_client.post("/api/users", json={
        "username": "hacker", "password": "password1", "role": "user",
    }).status_code == 403


def test_users_duplicate_username(api_client):
    make_user(api_client, "petr", "password1")
    r = api_client.post("/api/users", json={
        "username": "petr", "password": "password1", "role": "user",
    })
    assert r.status_code == 400


def test_users_cannot_delete_self(api_client):
    login(api_client, "admin", "adminpass123")
    assert api_client.delete("/api/users/1").status_code == 400


def test_users_cannot_demote_self(api_client):
    login(api_client, "admin", "adminpass123")
    assert api_client.put("/api/users/1", json={"role": "user"}).status_code == 400


def test_users_cannot_demote_self_to_manager(api_client):
    login(api_client, "admin", "adminpass123")
    assert api_client.put("/api/users/1", json={"role": "manager"}).status_code == 400


# ── Роль «Руководитель» (manager) ───────────────────────────
def test_manager_create_and_login(api_client):
    login(api_client, "admin", "adminpass123")
    r = api_client.post(
        "/api/users",
        json={"username": "boss", "password": "password1", "role": "manager", "full_name": "Шеф"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "manager"
    assert login(api_client, "boss", "password1").status_code == 200
    me = api_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "manager"


def test_manager_can_read_data(api_client):
    login(api_client, "admin", "adminpass123")
    api_client.post("/api/rows", json={"fio": "А", "date": "2026-09-01", "cash": 10})
    api_client.post(
        "/api/users",
        json={"username": "boss2", "password": "password1", "role": "manager"},
    )
    login(api_client, "boss2", "password1")
    assert api_client.get("/api/rows").status_code == 200
    assert api_client.get("/api/rows/periods").status_code == 200
    assert api_client.get("/api/rows/monthly").status_code == 200


def test_manager_cannot_write(api_client):
    login(api_client, "admin", "adminpass123")
    created = api_client.post(
        "/api/rows", json={"fio": "X", "date": "2026-09-01", "cash": 1}
    ).json()
    api_client.post(
        "/api/users",
        json={"username": "boss3", "password": "password1", "role": "manager"},
    )
    login(api_client, "boss3", "password1")
    row_id = created["id"]
    assert api_client.post("/api/rows", json={"fio": "X", "date": "2026-09-02"}).status_code == 403
    assert api_client.put(f"/api/rows/{row_id}", json={"fio": "Y"}).status_code == 403
    assert api_client.delete(f"/api/rows/{row_id}").status_code == 403
    assert api_client.post("/api/drivers/upload", json={"content": "Иванов\n"}).status_code == 403
    assert api_client.post("/api/routes/upload", json={"content": "10\n"}).status_code == 403
    assert api_client.delete("/api/drivers").status_code == 403
    assert api_client.delete("/api/routes").status_code == 403
    assert api_client.get("/api/rows/export").status_code == 403


def test_manager_no_admin_areas(api_client):
    login(api_client, "admin", "adminpass123")
    api_client.post(
        "/api/users",
        json={"username": "boss4", "password": "password1", "role": "manager"},
    )
    login(api_client, "boss4", "password1")
    assert api_client.get("/api/users").status_code == 403
    assert api_client.get("/api/audit").status_code == 403
    assert api_client.post("/api/rows/append", json={"rows": []}).status_code == 403
    assert api_client.post("/api/rows/replace", json={"rows": []}).status_code == 403
    assert api_client.post("/api/rows/check", json={"rows": []}).status_code == 403
    assert api_client.post("/api/rows/clear").status_code == 403


def test_users_short_password_rejected(api_client):
    login(api_client, "admin", "adminpass123")
    r = api_client.post("/api/users", json={
        "username": "shorty", "password": "123", "role": "user",
    })
    assert r.status_code == 422


def test_users_password_bytes_limit(api_client):
    login(api_client, "admin", "adminpass123")
    # 42 кириллических символа = 84 байта: bcrypt разрешает только 72 байта
    long_pw = "пароль" * 7
    assert len(long_pw.encode("utf-8")) > 72
    r = api_client.post("/api/users", json={
        "username": "longpw", "password": long_pw, "role": "user",
    })
    assert r.status_code == 422


# ── Записи выручки ──────────────────────────────────────────
def test_rows_crud(api_client):
    login(api_client, "admin", "adminpass123")
    created = api_client.post("/api/rows", json={
        "fio": "Иванов И.И.", "tab_num": "12", "date": "2026-09-01",
        "route": "10", "cash": 100, "card": 50.5, "card_av": 0,
    })
    assert created.status_code == 201
    row = created.json()
    assert row["total"] == 150.5
    rid = row["id"]

    rows = api_client.get("/api/rows").json()
    assert any(r["id"] == rid for r in rows)

    upd = api_client.put(f"/api/rows/{rid}", json={
        "fio": "Иванов И.И.", "tab_num": "12", "date": "2026-09-01",
        "route": "10", "cash": 200, "card": 0, "card_av": 0,
    })
    assert upd.status_code == 200
    assert upd.json()["total"] == 200

    assert api_client.delete(f"/api/rows/{rid}").status_code == 200
    assert all(r["id"] != rid for r in api_client.get("/api/rows").json())


def test_rows_date_filter(api_client):
    login(api_client, "admin", "adminpass123")
    for d in ("2026-09-01", "2026-09-02", "2026-09-10"):
        api_client.post("/api/rows", json={"fio": "Петров П.П.", "date": d, "cash": 10})
    assert len(api_client.get("/api/rows", params={"date": "2026-09-02"}).json()) == 1
    assert len(api_client.get("/api/rows", params={"start": "2026-09-02", "end": "2026-09-03"}).json()) == 1
    assert len(api_client.get("/api/rows", params={"fio": "петров"}).json()) == 3


def test_rows_import_replace(api_client):
    login(api_client, "admin", "adminpass123")
    api_client.post("/api/rows", json={"fio": "Старый", "date": "2026-01-01", "cash": 1})
    payload = {"rows": [
        {"fio": "Новый 1", "date": "2026-09-01", "cash": 10},
        {"fio": "Новый 2", "date": "2026-09-02", "card": 20},
    ]}
    r = api_client.post("/api/rows/replace", json=payload)
    assert r.status_code == 200
    assert len(r.json()) == 2
    assert {x["fio"] for x in r.json()} == {"Новый 1", "Новый 2"}


def test_rows_import_replace_admin_only(api_client):
    make_user(api_client, "ivan", "password1", role="user")
    login(api_client, "ivan", "password1")
    r = api_client.post("/api/rows/replace", json={"rows": [{"fio": "X", "date": "2026-09-01"}]})
    assert r.status_code == 403


def test_rows_periods(api_client):
    login(api_client, "admin", "adminpass123")
    for d, cash in (("2026-08-05", 10), ("2026-08-20", 20), ("2026-09-01", 5)):
        api_client.post("/api/rows", json={"fio": "Водитель", "date": d, "cash": cash})
    periods = api_client.get("/api/rows/periods").json()
    assert periods == [
        {"year": "2026", "month": "09", "count": 1},
        {"year": "2026", "month": "08", "count": 2},
    ]


def test_rows_clear_admin_only(api_client):
    make_user(api_client, "ivan", "password1", role="user")
    login(api_client, "ivan", "password1")
    assert api_client.post("/api/rows/clear").status_code == 403
    login(api_client, "admin", "adminpass123")
    assert api_client.post("/api/rows/clear").status_code == 200


def test_rows_require_auth(api_client):
    assert api_client.get("/api/rows").status_code == 401


# ── Дедупликация справочников ───────────────────────────────
def test_drivers_dedup(api_client):
    login(api_client, "admin", "adminpass123")
    content = "Иванов\t12\nПетров\t34\nИванов\t12\n\n"
    r = api_client.post("/api/drivers/upload", json={"content": content})
    assert r.status_code == 200
    assert r.json()["added"] == 2
    assert r.json()["total"] == 2

    r2 = api_client.post("/api/drivers/upload", json={"content": "Иванов\t12\nСидоров\t"})
    assert r2.json()["added"] == 1
    assert r2.json()["total"] == 3


def test_routes_dedup(api_client):
    login(api_client, "admin", "adminpass123")
    r = api_client.post("/api/routes/upload", json={"content": "10\n21\n10\n"})
    assert r.json()["added"] == 2
    assert r.json()["total"] == 2
    r2 = api_client.post("/api/routes/upload", json={"content": "10\n5\n"})
    assert r2.json()["added"] == 1
    assert r2.json()["total"] == 3


def test_drivers_require_auth(api_client):
    assert api_client.post("/api/drivers/upload", json={"content": "x\n"}).status_code == 401


# ── CSRF-защита ─────────────────────────────────────────────
def test_csrf_blocked(api_client):
    r = api_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "adminpass123"},
        headers={"Origin": "http://evil.example"},
    )
    assert r.status_code == 403


# ── Агрегация по месяцам ────────────────────────────────────
def test_rows_monthly(api_client):
    login(api_client, "admin", "adminpass123")
    api_client.post("/api/rows", json={"fio": "А", "date": "2026-08-05", "cash": 10})
    api_client.post("/api/rows", json={"fio": "Б", "date": "2026-09-01", "cash": 5, "card": 1})
    api_client.post("/api/rows", json={"fio": "В", "date": "2026-09-10", "card": 3})
    m = api_client.get("/api/rows/monthly", params={"year": "2026"}).json()
    assert m == [
        {"month": 8, "count": 1, "revenue": 10.0},
        {"month": 9, "count": 2, "revenue": 9.0},
    ]


# ── Дополняющий импорт /append ──────────────────────────────
def test_rows_append_admin_only(api_client):
    make_user(api_client, "ivan", "password1", role="user")
    login(api_client, "ivan", "password1")
    r = api_client.post("/api/rows/append", json={"rows": [{"fio": "X", "date": "2026-09-01"}]})
    assert r.status_code == 403


def test_rows_append_dedup(api_client):
    login(api_client, "admin", "adminpass123")
    base = {"fio": "Иванов И.", "tab_num": "1", "date": "2026-09-01", "route": "Р1", "cash": 10}
    api_client.post("/api/rows", json=base)
    r = api_client.post(
        "/api/rows/append",
        json={"rows": [base, {"fio": "Петров П.", "date": "2026-09-02", "cash": 20}]},
    )
    res = r.json()
    assert res["added"] == 1
    assert res["skipped"] == 1
    assert res["total"] == 2
    assert len(res["duplicates"]) == 1
    assert res["duplicates"][0]["fio"] == "Иванов И."
    assert len(api_client.get("/api/rows").json()) == 2


# ── Проверка дублей /rows/check + импорт с дублями ──────────
def test_rows_check_returns_duplicates(api_client):
    login(api_client, "admin", "adminpass123")
    base = {"fio": "Иванов И.", "tab_num": "1", "date": "2026-09-01", "route": "Р1", "cash": 10}
    api_client.post("/api/rows", json=base)
    r = api_client.post(
        "/api/rows/check",
        json={"rows": [base, {"fio": "Петров П.", "date": "2026-09-02", "cash": 20}, base]},
    )
    assert r.status_code == 200
    res = r.json()
    assert res["duplicates_count"] == 2  # дубль из базы + дубль внутри файла
    assert [d["fio"] for d in res["duplicates"]] == ["Иванов И.", "Иванов И."]
    assert len(api_client.get("/api/rows").json()) == 1  # проверка ничего не записала


def test_rows_check_admin_only(api_client):
    make_user(api_client, "ivan", "password1", role="user")
    login(api_client, "ivan", "password1")
    r = api_client.post("/api/rows/check", json={"rows": [{"fio": "X", "date": "2026-09-01"}]})
    assert r.status_code == 403


def test_rows_append_include_duplicates(api_client):
    login(api_client, "admin", "adminpass123")
    base = {"fio": "Иванов И.", "tab_num": "1", "date": "2026-09-01", "route": "Р1", "cash": 10}
    api_client.post("/api/rows", json=base)
    r = api_client.post(
        "/api/rows/append?include_duplicates=true",
        json={"rows": [base, {"fio": "Петров П.", "date": "2026-09-02", "cash": 20}]},
    )
    res = r.json()
    assert res["added"] == 2
    assert res["skipped"] == 0
    assert len(res["duplicates"]) == 1
    assert len(api_client.get("/api/rows").json()) == 3


# ── Экспорт всех записей ────────────────────────────────────
def test_rows_export_csv_admin(api_client):
    login(api_client, "admin", "adminpass123")
    api_client.post("/api/rows", json={"fio": "А", "date": "2026-09-01", "cash": 10.5})
    r = api_client.get("/api/rows/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    text = r.content.decode("utf-8-sig")
    assert text.startswith("ФИО;Таб. №;Дата;Маршрут;Наличные;Безнал;Безнал АВ;Всего;Кто добавил;Когда")
    assert "А;;2026-09-01;;10,50;0,00;0,00;10,50;admin" in text


def test_rows_export_csv_user(api_client):
    make_user(api_client, "ivan", "password1", role="user")
    login(api_client, "admin", "adminpass123")
    api_client.post("/api/rows", json={"fio": "А", "date": "2026-09-01", "cash": 5})
    login(api_client, "ivan", "password1")
    r = api_client.get("/api/rows/export")
    assert r.status_code == 200
    text = r.content.decode("utf-8-sig")
    assert text.startswith("ФИО;Таб. №;Дата;Маршрут;Наличные;Безнал;Безнал АВ;Всего")
    assert "Кто добавил" not in text


# ── Журнал действий ─────────────────────────────────────────
def test_audit_requires_admin(api_client):
    assert api_client.get("/api/audit").status_code == 401
    make_user(api_client, "ivan", "password1", role="user")
    login(api_client, "ivan", "password1")
    assert api_client.get("/api/audit").status_code == 403


def test_audit_records(api_client):
    make_user(api_client, "ivan", "password1", role="user")
    login(api_client, "admin", "adminpass123")
    api_client.post("/api/rows/clear")
    api_client.post("/api/rows/append", json={"rows": [{"fio": "А", "date": "2026-09-01"}]})
    logs = api_client.get("/api/audit").json()
    actions = [l["action"] for l in logs]
    assert "users.create" in actions
    assert "rows.clear" in actions
    assert "rows.append" in actions
    assert all(l["username"] in ("admin", "ivan") for l in logs)


# ── Разделители в справочнике водителей ─────────────────────
def test_drivers_upload_delimiter(api_client):
    login(api_client, "admin", "adminpass123")
    r = api_client.post("/api/drivers/upload", json={"content": "Иванов И.;12\nПетров П.,34\n"})
    assert r.status_code == 200
    drivers = r.json()["drivers"]
    assert {"fio": "Иванов И.", "tab_num": "12"} in drivers
    assert {"fio": "Петров П.", "tab_num": "34"} in drivers
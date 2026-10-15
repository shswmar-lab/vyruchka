import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app import audit
from app import db
from app.auth import get_current_user, require_admin, require_editor
from app.schemas import ReplaceRequest, RowIn

router = APIRouter(prefix="/rows", tags=["rows"])


def _out(r: dict) -> dict:
    for k in ("cash", "card", "card_av"):
        r[k] = round(r[k] or 0, 2)
    r["total"] = round((r["cash"] or 0) + (r["card"] or 0) + (r["card_av"] or 0), 2)
    return r


def _money(v) -> str:
    return f"{round(v or 0, 2):.2f}".replace(".", ",")


def _row_key(r) -> tuple:
    return (r.fio.strip().lower(), r.tab_num.strip(), r.date.strip(), r.route.strip())


def _duplicate_out(r) -> dict:
    return {
        "fio": r.fio.strip(),
        "tab_num": r.tab_num.strip(),
        "date": r.date.strip(),
        "route": r.route.strip(),
        "cash": round(r.cash, 2),
        "card": round(r.card, 2),
        "card_av": round(r.card_av, 2),
    }


def _load_db_keys() -> set:
    return {
        (r["fio"].lower(), r["tab_num"], r["date"], r["route"])
        for r in db.query_all("SELECT fio, tab_num, date, route FROM rows")
    }


@router.get("")
def list_rows(
    fio: str = Query(""),
    date: str = Query(""),
    start: str = Query(""),
    end: str = Query(""),
    user: dict = Depends(get_current_user),
):
    # Фильтры по дате выполняем в SQL (формат ISO, регистр не важен).
    sql = "SELECT * FROM rows WHERE 1 = 1"
    params: list = []
    if date:
        sql += " AND date = ?"
        params.append(date)
    if start:
        sql += " AND date >= ?"
        params.append(start)
    if end:
        sql += " AND date <= ?"
        params.append(end)
    sql += " ORDER BY date DESC, id DESC"
    rows = db.query_all(sql, tuple(params))
    # Фильтр по ФИО — в Python: SQLite LIKE не регистронезависим для кириллицы.
    if fio:
        needle = fio.strip().lower()
        rows = [r for r in rows if needle in r["fio"].lower()]
    return [_out(r) for r in rows]


@router.get("/periods")
def list_periods(user: dict = Depends(get_current_user)):
    """Периоды (год/месяц) с количеством записей — для меню выбора месяца."""
    return db.query_all(
        """SELECT substr(date, 1, 4) AS year,
                  substr(date, 6, 2) AS month,
                  COUNT(*)           AS count
           FROM rows
           GROUP BY year, month
           ORDER BY year DESC, month DESC"""
    )


@router.get("/monthly")
def monthly_rows(year: str = Query(""), user: dict = Depends(get_current_user)):
    """Суммарно по месяцам за год — для диаграммы."""
    sql = (
        "SELECT CAST(substr(date, 6, 2) AS INTEGER) AS month,"
        "       COUNT(*)                                        AS count,"
        "       ROUND(SUM(COALESCE(cash,0) + COALESCE(card,0) + COALESCE(card_av,0)), 2) AS revenue"
        "  FROM rows WHERE 1 = 1"
    )
    params: list = []
    if year:
        sql += " AND substr(date, 1, 4) = ?"
        params.append(year)
    sql += " GROUP BY month ORDER BY month"
    return db.query_all(sql, tuple(params))


@router.get("/export")
def export_rows_csv(user: dict = Depends(require_editor)):
    """Все записи в CSV (разделитель «;», десятичная запятая; BOM для Excel)."""
    rows = db.query_all("SELECT * FROM rows ORDER BY date DESC, id DESC")
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    header = ["ФИО", "Таб. №", "Дата", "Маршрут", "Наличные", "Безнал", "Безнал АВ", "Всего"]
    if user["role"] == "admin":
        header += ["Кто добавил", "Когда"]
    w.writerow(header)
    for r in rows:
        line = [
            r["fio"], r["tab_num"], r["date"], r["route"],
            _money(r["cash"]), _money(r["card"]), _money(r["card_av"]),
            _money(r["cash"] + r["card"] + r["card_av"]),
        ]
        if user["role"] == "admin":
            line += [r["created_by"], r["created_at"]]
        w.writerow(line)
    data = "\ufeff" + buf.getvalue()
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="vyruchka_all.csv"'},
    )


@router.post("", status_code=201)
def create_row(payload: RowIn, user: dict = Depends(require_editor)):
    row = payload.model_dump()
    row["created_by"] = user["username"]
    row["created_at"] = datetime.now(timezone.utc).isoformat()
    new_id = db.execute(
        """INSERT INTO rows (fio, tab_num, date, route, cash, card, card_av, created_by, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            row["fio"].strip(),
            row["tab_num"].strip(),
            row["date"].strip(),
            row["route"].strip(),
            round(row["cash"], 2),
            round(row["card"], 2),
            round(row["card_av"], 2),
            row["created_by"],
            row["created_at"],
        ),
    )
    created = db.query_one("SELECT * FROM rows WHERE id = ?", (new_id,))
    return _out(created)


@router.put("/{row_id}")
def update_row(row_id: int, payload: RowIn, user: dict = Depends(require_editor)):
    existing = db.query_one("SELECT id FROM rows WHERE id = ?", (row_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    row = payload.model_dump()
    db.execute(
        """UPDATE rows SET fio = ?, tab_num = ?, date = ?, route = ?, cash = ?, card = ?, card_av = ?
           WHERE id = ?""",
        (
            row["fio"].strip(),
            row["tab_num"].strip(),
            row["date"].strip(),
            row["route"].strip(),
            round(row["cash"], 2),
            round(row["card"], 2),
            round(row["card_av"], 2),
            row_id,
        ),
    )
    updated = db.query_one("SELECT * FROM rows WHERE id = ?", (row_id,))
    return _out(updated)


@router.delete("/{row_id}")
def delete_row(row_id: int, user: dict = Depends(require_editor)):
    existing = db.query_one("SELECT id FROM rows WHERE id = ?", (row_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    db.execute("DELETE FROM rows WHERE id = ?", (row_id,))
    return {"ok": True}


@router.post("/replace")
def replace_rows(payload: ReplaceRequest, admin: dict = Depends(require_admin)):
    """Полная замена всех записей (импорт из Excel). Только администратор."""
    created_at = datetime.now(timezone.utc).isoformat()
    entries = [
        (
            r.fio.strip(),
            r.tab_num.strip(),
            r.date.strip(),
            r.route.strip(),
            round(r.cash, 2),
            round(r.card, 2),
            round(r.card_av, 2),
            admin["username"],
            created_at,
        )
        for r in payload.rows
    ]
    with db.connect() as conn:
        conn.execute("DELETE FROM rows")
        conn.executemany(
            """INSERT INTO rows (fio, tab_num, date, route, cash, card, card_av, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            entries,
        )
    rows = db.query_all("SELECT * FROM rows ORDER BY date DESC, id DESC")
    audit.log_action(admin["username"], "rows.replace", f"импорт {len(payload.rows)} записей")
    return [_out(r) for r in rows]


@router.post("/check")
def check_duplicates(payload: ReplaceRequest, admin: dict = Depends(require_admin)):
    """Проверка строк на дубли по fio|tab_num|date|route без записи в базу.
    Дубли считаются относительно существующей базы и внутри файла.
    Только администратор."""
    existing = _load_db_keys()
    seen = set(existing)
    duplicates = []
    for r in payload.rows:
        key = _row_key(r)
        if key in seen:
            duplicates.append(_duplicate_out(r))
            continue
        seen.add(key)
    return {"duplicates": duplicates, "duplicates_count": len(duplicates)}


@router.post("/append")
def append_rows(
    payload: ReplaceRequest,
    include_duplicates: bool = Query(False),
    admin: dict = Depends(require_admin),
):
    """Дополнить базу строками с дедупликацией по fio|tab_num|date|route.
    Если include_duplicates=true — вставить все строки, включая дубли.
    Только администратор."""
    existing = _load_db_keys()
    seen = set(existing)
    created_at = datetime.now(timezone.utc).isoformat()
    added = 0
    duplicates = []
    with db.connect() as conn:
        for r in payload.rows:
            key = _row_key(r)
            is_dup = key in seen
            if is_dup:
                duplicates.append(_duplicate_out(r))
                if not include_duplicates:
                    continue
            conn.execute(
                """INSERT INTO rows (fio, tab_num, date, route, cash, card, card_av, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    r.fio.strip(),
                    r.tab_num.strip(),
                    r.date.strip(),
                    r.route.strip(),
                    round(r.cash, 2),
                    round(r.card, 2),
                    round(r.card_av, 2),
                    admin["username"],
                    created_at,
                ),
            )
            added += 1
            seen.add(key)
    skipped = len(payload.rows) - added
    total = db.query_one("SELECT COUNT(*) AS c FROM rows")["c"]
    detail = f"добавлено {added}, пропущено {skipped}"
    if include_duplicates:
        detail += ", включая дубли"
    audit.log_action(admin["username"], "rows.append", detail)
    return {"added": added, "skipped": skipped, "total": total, "duplicates": duplicates}


@router.post("/clear")
def clear_rows(admin: dict = Depends(require_admin)):
    """Полностью очистить все записи. Только администратор."""
    with db.connect() as conn:
        conn.execute("DELETE FROM rows")
    audit.log_action(admin["username"], "rows.clear", "очистка всех записей")
    return {"ok": True, "total": 0}
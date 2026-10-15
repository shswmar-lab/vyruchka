from fastapi import APIRouter, Depends, HTTPException

from app import audit
from app import db
from app.auth import require_admin
from app.schemas import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

FIELDS = "id, username, role, full_name, is_active, created_at"


def _out(u: dict) -> dict:
    return {k: u[k] for k in FIELDS.split(", ")}


@router.get("")
def list_users(user: dict = Depends(require_admin)):
    rows = db.query_all(f"SELECT {FIELDS} FROM users ORDER BY id")
    return [_out(r) for r in rows]


@router.post("", status_code=201)
def create_user(payload: UserCreate, user: dict = Depends(require_admin)):
    dup = db.query_one("SELECT id FROM users WHERE username = ?", (payload.username,))
    if dup:
        raise HTTPException(status_code=400, detail="Логин уже занят")
    from datetime import datetime, timezone

    from app.auth import hash_password

    db.execute(
        """INSERT INTO users (username, password_hash, role, full_name, is_active, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            payload.username,
            hash_password(payload.password),
            payload.role,
            payload.full_name,
            1 if payload.is_active else 0,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    created = db.query_one(f"SELECT {FIELDS} FROM users WHERE username = ?", (payload.username,))
    audit.log_action(user["username"], "users.create", f"{payload.username} ({payload.role})")
    return _out(created)


@router.put("/{user_id}")
def update_user(user_id: int, payload: UserUpdate, admin: dict = Depends(require_admin)):
    target = db.query_one(f"SELECT {FIELDS} FROM users WHERE id = ?", (user_id,))
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Защита от блокировки самого себя / снятия роли админа с себя
    if target["id"] == admin["id"]:
        if payload.is_active is False:
            raise HTTPException(status_code=400, detail="Нельзя заблокировать свою учётную запись")
        if payload.role is not None and payload.role != "admin":
            raise HTTPException(status_code=400, detail="Нельзя снять роль администратора с себя")

    sets, params = [], []
    if payload.full_name is not None:
        sets.append("full_name = ?")
        params.append(payload.full_name.strip())
    if payload.is_active is not None:
        sets.append("is_active = ?")
        params.append(1 if payload.is_active else 0)
    if payload.role is not None:
        sets.append("role = ?")
        params.append(payload.role)
    if payload.password:
        from app.auth import hash_password

        sets.append("password_hash = ?")
        params.append(hash_password(payload.password))

    if not sets:
        return _out(target)

    params.append(user_id)
    db.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", tuple(params))
    updated = db.query_one(f"SELECT {FIELDS} FROM users WHERE id = ?", (user_id,))
    audit.log_action(admin["username"], "users.update", f"id={user_id} {target['username']}")
    return _out(updated)


@router.delete("/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Нельзя удалить свою учётную запись")
    target = db.query_one(f"SELECT {FIELDS} FROM users WHERE id = ?", (user_id,))
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    audit.log_action(admin["username"], "users.delete", f"id={user_id} {target['username']}")
    return {"ok": True}
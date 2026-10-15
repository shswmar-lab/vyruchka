import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request

from app import db

COOKIE_NAME = "vyruchka_token"
ALG = "HS256"
MAX_AGE = 7 * 24 * 3600  # 7 дней


def get_secret_key() -> str:
    return os.environ.get("SECRET_KEY", "dev-secret-change-me")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(seconds=MAX_AGE),
    }
    return jwt.encode(payload, get_secret_key(), algorithm=ALG)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, get_secret_key(), algorithms=[ALG])
    except jwt.PyJWTError:
        return None


USER_FIELDS = "id, username, role, full_name, is_active, created_at"


def get_current_user(request: Request) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Не авторизован")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Недействительный токен")
    user = db.query_one(
        f"SELECT {USER_FIELDS} FROM users WHERE id = ?",
        (payload.get("sub"),),
    )
    if not user or not user["is_active"]:
        raise HTTPException(status_code=401, detail="Пользователь заблокирован или не найден")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    return user


def require_editor(user: dict = Depends(get_current_user)) -> dict:
    """Доступ к записи данных: администратор и пользователь (не «Руководитель»)."""
    if user["role"] not in ("admin", "user"):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    return user
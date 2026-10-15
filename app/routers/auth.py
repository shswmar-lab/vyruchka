import os

from fastapi import APIRouter, Depends, HTTPException, Response

from app import db
from app.auth import (
    COOKIE_NAME,
    MAX_AGE,
    USER_FIELDS,
    create_token,
    get_current_user,
    verify_password,
)
from app.schemas import LoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    user = db.query_one("SELECT * FROM users WHERE username = ?", (payload.username,))
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Учётная запись заблокирована")

    token = create_token(user["id"])
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=(os.environ.get("COOKIE_SECURE", "false").lower() == "true"),
        path="/",
    )
    return _user_out(user)


@router.get("/users")
def public_user_list():
    """Активные логины для формы входа (без авторизации)."""
    return [{"username": r["username"]}
            for r in db.query_all(
                "SELECT username FROM users WHERE is_active = 1 ORDER BY username COLLATE NOCASE"
            )]


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


def _user_out(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "full_name": user["full_name"],
        "is_active": user["is_active"],
        "created_at": user["created_at"],
    }
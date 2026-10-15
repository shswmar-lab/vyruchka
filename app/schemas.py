from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


def _password_le_72_bytes(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Пароль слишком длинный — максимум 72 байта")
    return value


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=72)


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[\w.\-@]+$")
    password: str = Field(min_length=8, max_length=72)
    role: Literal["admin", "user", "manager"] = "user"
    full_name: str = Field(default="", max_length=150)
    is_active: bool = True

    _password_ok = field_validator("password")(_password_le_72_bytes)


class UserUpdate(BaseModel):
    password: Optional[str] = Field(default=None, min_length=8, max_length=72)
    role: Optional[Literal["admin", "user", "manager"]] = None
    full_name: Optional[str] = Field(default=None, max_length=150)
    is_active: Optional[bool] = None

    _password_ok = field_validator("password")(_password_le_72_bytes)


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    full_name: str
    is_active: bool
    created_at: str


class RowIn(BaseModel):
    fio: str = Field(min_length=1, max_length=200)
    tab_num: str = Field(default="", max_length=50)
    date: str = Field(default="", max_length=10)
    route: str = Field(default="", max_length=200)
    cash: float = Field(default=0, ge=0)
    card: float = Field(default=0, ge=0)
    card_av: float = Field(default=0, ge=0)


class ReplaceRequest(BaseModel):
    rows: list[RowIn]


class FileContent(BaseModel):
    content: str
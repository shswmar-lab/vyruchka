"""Создание первичного администратора.

Использование (на сервере, от имени сервисного пользователя):
    cd /opt/vyruchka
    venv/bin/python -m app.create_admin

Параметры берутся из окружения (см. .env):
    ADMIN_USERNAME, ADMIN_PASSWORD
Если пароль не задан — генерируется и выводится в консоль.
"""

import os
import secrets
import string
from datetime import datetime, timezone

from app import db
from app.auth import hash_password


def main() -> None:
    db.init_db()

    username = (os.environ.get("ADMIN_USERNAME") or "admin").strip()
    password = os.environ.get("ADMIN_PASSWORD") or ""

    existing = db.query_one("SELECT id, role FROM users WHERE username = ?", (username,))
    if existing:
        print(f"Пользователь '{username}' уже существует (id={existing['id']}, role={existing['role']}). Пропуск.")
        return

    generated = False
    if not password:
        alphabet = string.ascii_letters + string.digits
        password = "".join(secrets.choice(alphabet) for _ in range(16))
        generated = True

    db.execute(
        """INSERT INTO users (username, password_hash, role, full_name, is_active, created_at)
           VALUES (?, ?, 'admin', 'Администратор', 1, ?)""",
        (username, hash_password(password), datetime.now(timezone.utc).isoformat()),
    )

    if generated:
        print(f"Создан администратор: {username}")
        print(f"Сгенерированный пароль: {password}")
        print("Запишите его сейчас, затем смените пароль в разделе «Администрирование».")
    else:
        print(f"Создан администратор: {username} (пароль из .env).")


if __name__ == "__main__":
    main()
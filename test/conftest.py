import os

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")


@pytest.fixture()
def api_client(tmp_path):
    from fastapi.testclient import TestClient

    from app import db, main
    from app.auth import hash_password

    os.environ["DB_PATH"] = str(tmp_path / "test.db")
    db.init_db()

    db.execute(
        """INSERT INTO users (username, password_hash, role, full_name, is_active, created_at)
           VALUES (?, ?, ?, ?, 1, ?)""",
        ("admin", hash_password("adminpass123"), "admin", "Администратор", "2026-01-01T00:00:00"),
    )

    with TestClient(main.app) as client:
        yield client
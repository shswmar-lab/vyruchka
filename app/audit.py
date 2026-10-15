from datetime import datetime, timezone

from app import db


def log_action(username: str, action: str, detail: str = "") -> None:
    """Записать строку в журнал действий."""
    db.execute(
        """INSERT INTO audit_log (username, action, detail, created_at)
           VALUES (?, ?, ?, ?)""",
        (username or "", action, detail, datetime.now(timezone.utc).isoformat()),
    )
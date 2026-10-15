from fastapi import APIRouter, Depends

from app import db
from app.auth import get_current_user, require_editor
from app.schemas import FileContent

router = APIRouter(prefix="/routes", tags=["routes"])


@router.get("")
def list_routes(user: dict = Depends(get_current_user)):
    return db.query_all("SELECT name FROM routes ORDER BY name")


@router.post("/upload")
def upload_routes(payload: FileContent, user: dict = Depends(require_editor)):
    """Загрузка справочника маршрутов из текста. Формат: одна строка — один маршрут."""
    existing = {r["name"].lower() for r in db.query_all("SELECT name FROM routes")}
    added, entries = 0, []
    for raw in payload.content.splitlines():
        name = raw.strip()
        if not name:
            continue
        key = name.lower()
        if key in existing:
            continue
        existing.add(key)
        added += 1
        entries.append((name,))

    with db.connect() as conn:
        conn.executemany("INSERT OR IGNORE INTO routes (name) VALUES (?)", entries)

    rows = db.query_all("SELECT name FROM routes ORDER BY name")
    return {"routes": rows, "total": len(rows), "added": added}


@router.delete("")
def clear_routes(user: dict = Depends(require_editor)):
    with db.connect() as conn:
        conn.execute("DELETE FROM routes")
    return {"ok": True, "total": 0}
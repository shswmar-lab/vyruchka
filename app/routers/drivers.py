from fastapi import APIRouter, Depends
import re

from app import db
from app.auth import get_current_user, require_editor
from app.schemas import FileContent

router = APIRouter(prefix="/drivers", tags=["drivers"])

_TAB_RE = re.compile(r"[\t;,]+")


@router.get("")
def list_drivers(user: dict = Depends(get_current_user)):
    return db.query_all("SELECT fio, tab_num FROM drivers ORDER BY fio")


@router.post("/upload")
def upload_drivers(payload: FileContent, user: dict = Depends(require_editor)):
    """Загрузка справочника водителей из текста. Формат строки: ФИО<разделитель>Таб.№
    (разделитель — таб, запятая или точка с запятой)."""
    existing = {r["fio"].lower() for r in db.query_all("SELECT fio FROM drivers")}
    added, entries = 0, []
    for raw in payload.content.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = _TAB_RE.split(line, maxsplit=1)
        fio = parts[0].strip()
        if not fio:
            continue
        key = fio.lower()
        if key in existing:
            continue
        existing.add(key)
        added += 1
        tab_num = parts[1].strip() if len(parts) > 1 else ""
        entries.append((fio, tab_num))

    with db.connect() as conn:
        conn.executemany("INSERT OR IGNORE INTO drivers (fio, tab_num) VALUES (?, ?)", entries)

    rows = db.query_all("SELECT fio, tab_num FROM drivers ORDER BY fio")
    return {"drivers": rows, "total": len(rows), "added": added}


@router.delete("")
def clear_drivers(user: dict = Depends(require_editor)):
    with db.connect() as conn:
        conn.execute("DELETE FROM drivers")
    return {"ok": True, "total": 0}
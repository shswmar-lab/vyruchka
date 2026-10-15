from fastapi import APIRouter, Depends, Query

from app import db
from app.auth import require_admin

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit(limit: int = Query(500, ge=1, le=2000), admin: dict = Depends(require_admin)):
    """Журнал действий администратора (только для админа)."""
    return db.query_all(
        "SELECT id, username, action, detail, created_at FROM audit_log "
        "ORDER BY id DESC LIMIT ?",
        (limit,),
    )
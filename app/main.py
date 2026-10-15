import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.routers import auth, audit, drivers, routes, rows, users

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
ENABLE_DOCS = os.environ.get("ENABLE_DOCS", "false").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


def make_app() -> FastAPI:
    app = FastAPI(
        title="Выручка водителей",
        docs_url="/docs" if ENABLE_DOCS else None,
        redoc_url=None,
        openapi_url="/openapi.json" if ENABLE_DOCS else None,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def csrf_protection(request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            origin = request.headers.get("origin")
            if origin:
                o = urlparse(origin)
                if o.hostname and o.hostname != request.url.hostname:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Cross-origin request blocked"},
                    )
        return await call_next(request)

    app.include_router(auth.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(rows.router, prefix="/api")
    app.include_router(drivers.router, prefix="/api")
    app.include_router(routes.router, prefix="/api")
    app.include_router(audit.router, prefix="/api")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = make_app()
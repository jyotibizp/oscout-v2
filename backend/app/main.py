from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.access import viewer_guard
from app.api.routes import router, system_callback
from app.core.logging import setup_logging
from app.core.settings import get_settings
from app.db.session import Base, get_engine
from app.scanner.scheduler import auto_scanner


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    setup_logging(s.log_level, s.log_json)
    engine = get_engine()
    if engine.url.get_backend_name() == "sqlite":
        import app.db.models  # noqa: F401
        Base.metadata.create_all(engine)  # dev convenience; PostgreSQL uses Alembic migrations
    if s.start_scheduler:
        auto_scanner.start()
    yield
    await auto_scanner.stop()


app = FastAPI(title="oscout v2 — ADX Signal Generator", version="1.0.0", lifespan=lifespan)
app.middleware("http")(viewer_guard)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in get_settings().cors_origins.split(",")],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


# The Kite Connect app's registered redirect URL is http://127.0.0.1:8000/auth/callback (no /api prefix)
app.add_api_route("/auth/callback", system_callback, methods=["GET"], include_in_schema=False)


@app.get("/health")
def health():
    return {"status": "ok"}


def mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built UI (npm run build) on the same origin; unknown non-API paths return index.html for client routes."""
    if not (dist / "index.html").is_file():
        return
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.split("/")[0] in {"api", "auth", "health"}:
            raise HTTPException(404)
        f = (dist / path).resolve()
        if path and f.is_file() and f.is_relative_to(dist):
            return FileResponse(f)
        return FileResponse(dist / "index.html")


mount_frontend(app, (Path(__file__).resolve().parent.parent / get_settings().frontend_dist).resolve())

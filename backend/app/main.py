from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
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
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in get_settings().cors_origins.split(",")],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}

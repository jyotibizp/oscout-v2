"""Structured (JSON-lines) application logging. Use log.info("event", extra={"ctx": {...}})."""
import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "level": record.levelname,
               "logger": record.name, "msg": record.getMessage()}
        ctx = getattr(record, "ctx", None)
        if ctx:
            out.update(ctx)
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


def setup_logging(level: str = "INFO", as_json: bool = True) -> None:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter() if as_json else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [h]
    root.setLevel(level)
    logging.getLogger("uvicorn.access").setLevel("WARNING")

from contextvars import ContextVar
from datetime import UTC, datetime
import json
import logging
import os
from typing import Any

from .config import Settings

try:
    # Optional dependency; enabled only if installed and LOKI_URL is set
    import logging_loki  # type: ignore
except Exception:  # pragma: no cover - optional import
    logging_loki = None  # type: ignore


# Context variable populated by middleware
REQUEST_ID_CTX: ContextVar[str | None] = ContextVar("request_id", default=None)


def _iso_utc_now() -> str:
    return datetime.now(UTC).isoformat()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload: dict[str, Any] = {
            "ts": _iso_utc_now(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }

        # Extra attributes commonly used
        if hasattr(record, "request_id") and record.request_id:
            payload["request_id"] = record.request_id
        if hasattr(record, "path") and record.path:
            payload["path"] = record.path
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


class RequestIdFilter(logging.Filter):
    """Injects request_id into log records when present in record.__dict__."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        # Prefer existing attribute, otherwise inject from contextvar
        if not hasattr(record, "request_id") or record.request_id is None:
            try:
                record.request_id = REQUEST_ID_CTX.get()  # type: ignore[attr-defined]
            except Exception:
                record.request_id = None  # type: ignore[attr-defined]
        return True


def setup_logging(settings: Settings) -> None:
    """Configure root logging for JSON console and optional Loki.

    Controlled by environment variables:
    - LOG_LEVEL (default: INFO)
    - LOKI_URL (if set, enable Loki handler)
    - LOKI_TENANT_ID (optional; multi-tenant Loki setups)
    """

    root = logging.getLogger()
    # Avoid duplicate handlers on reloads (e.g., tests/uvicorn workers)
    if getattr(root, "_acflp_logging_configured", False):  # type: ignore[attr-defined]
        return

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    root.setLevel(level)

    json_formatter = JsonFormatter()
    req_filter = RequestIdFilter()

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(json_formatter)
    console.addFilter(req_filter)
    root.addHandler(console)

    # Loki handler (optional)
    loki_url = os.getenv("LOKI_URL")
    if loki_url and logging_loki is not None:
        try:
            tags = {
                "service": getattr(settings, "APP_NAME", "acflp-backend"),
                "env": getattr(settings, "ENVIRONMENT", "production").value
                if hasattr(settings, "ENVIRONMENT")
                else "production",
                "version": getattr(settings, "APP_VERSION", "") or "",
            }
            tenant_id = os.getenv("LOKI_TENANT_ID")
            auth_user = os.getenv("LOKI_USERNAME")
            auth = (auth_user, os.getenv("LOKI_PASSWORD")) if auth_user else None

            common_kwargs: dict[str, Any] = {
                "url": loki_url,
                "version": "1",
                "tags": tags,
                "auth": auth,
            }

            try:
                # Try newer API with tenant_id support
                if tenant_id:
                    loki_handler = logging_loki.LokiHandler(tenant_id=tenant_id, **common_kwargs)  # type: ignore[attr-defined]
                else:
                    loki_handler = logging_loki.LokiHandler(**common_kwargs)  # type: ignore[attr-defined]
            except TypeError:
                # Fallback for older python-logging-loki versions
                loki_handler = logging_loki.LokiHandler(**common_kwargs)  # type: ignore[attr-defined]
                if tenant_id:
                    logging.getLogger(__name__).info(
                        "LOKI_TENANT_ID set but ignored: installed python-logging-loki lacks tenant_id support"
                    )

            loki_handler.setFormatter(json_formatter)
            loki_handler.addFilter(req_filter)
            root.addHandler(loki_handler)
        except Exception:  # pragma: no cover - defensive; do not break app
            logging.getLogger(__name__).warning("Failed to initialize Loki logging handler", exc_info=True)

    # Mark configured
    root._acflp_logging_configured = True  # type: ignore[attr-defined]

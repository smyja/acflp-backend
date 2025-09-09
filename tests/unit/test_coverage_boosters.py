from __future__ import annotations


def test_import_core_db_models() -> None:
    # Importing defines mixin classes; ensures module is loaded and covered
    from src.app.core.db import models

    assert hasattr(models, "UUIDMixin")
    assert hasattr(models, "TimestampMixin")
    assert hasattr(models, "SoftDeleteMixin")


def test_import_worker_settings() -> None:
    # Import worker settings to cover settings and functions modules
    from src.app.core.worker import settings as worker_settings

    assert hasattr(worker_settings, "WorkerSettings")
    ws = worker_settings.WorkerSettings
    # Verify expected attributes exist without invoking external services
    assert hasattr(ws, "functions")
    assert hasattr(ws, "redis_settings")

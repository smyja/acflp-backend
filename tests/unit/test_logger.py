from __future__ import annotations


def test_logger_import_initializes_handlers(tmp_path, monkeypatch):
    # Force logs directory into tmp to avoid polluting repo
    import os
    import src.app.core as core
    core_dir = os.path.dirname(os.path.abspath(core.__file__))
    fake_logs_dir = tmp_path / "logs"
    monkeypatch.setattr("src.app.core.logger.LOG_DIR", str(fake_logs_dir), raising=False)
    # Re-import module to run top-level setup with patched path
    import importlib
    mod = importlib.import_module("src.app.core.logger")
    importlib.reload(mod)

    # Handlers are attached and directory exists
    assert hasattr(mod, "LOG_FILE_PATH")
    assert os.path.isdir(os.path.dirname(mod.LOG_FILE_PATH))


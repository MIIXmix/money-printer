"""Shared test setup: isolate the DB and create the single master account once,
before any test module imports the app (which freezes settings at import time)."""

import os
import tempfile
from uuid import uuid4

os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.gettempdir(), f"kft_test_{uuid4().hex}.db"))
os.environ.setdefault("APP_SECRET", "test-secret-" + uuid4().hex)

from backend.app.db import init_db  # noqa: E402
from backend.app.auth import is_initialized, setup_master  # noqa: E402

MASTER_PASSWORD = "master-pass-123"

init_db()
if not is_initialized():
    setup_master(MASTER_PASSWORD)

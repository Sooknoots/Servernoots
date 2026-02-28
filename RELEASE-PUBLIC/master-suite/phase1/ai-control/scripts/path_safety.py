#!/usr/bin/env python3
import os
import tempfile
from pathlib import Path


def ensure_writable_env_path(var_name: str, default_path: str, fallback_path: str | Path) -> Path:
    configured = str(os.getenv(var_name, default_path) or "").strip() or str(default_path)
    configured_path = Path(configured)

    try:
        configured_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=str(configured_path.parent), prefix=".perm-check-", delete=True):
            pass
        return configured_path
    except Exception:
        fallback = Path(fallback_path)
        fallback.parent.mkdir(parents=True, exist_ok=True)
        os.environ[var_name] = str(fallback)
        return fallback

"""One indicator per user and interface: autostart plus a manual launch must not give two icons."""
from __future__ import annotations

import fcntl
import os
import tempfile
from pathlib import Path
from typing import IO


def lock_path(interface: str) -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    return Path(base) / f"wireguard-indicator-{os.getuid()}-{interface}.lock"


def acquire_lock(path: Path) -> IO[str] | None:
    """Return the open, locked file (keep a reference to it), or None if another instance holds it.

    flock is released by the kernel when the process dies, so a crash never leaves a stale lock.
    """
    handle = open(path, "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle

"""One indicator per user and interface: autostart plus a manual launch must not give two icons."""
from __future__ import annotations

import fcntl
import os
from pathlib import Path
from typing import IO


def lock_path(interface: str) -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR")
    if not base:
        # /tmp is shared and predictable, so fall back to a private per-user dir.
        base = Path.home() / ".cache" / "wireguard-indicator"
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
    return Path(base) / f"wireguard-indicator-{os.getuid()}-{interface}.lock"


def acquire_lock(path: Path) -> IO[str] | None:
    """Return the open, locked file (keep a reference to it), or None if it can't be locked.

    flock is released by the kernel when the process dies, so a crash never leaves a stale
    lock. O_NOFOLLOW and no O_TRUNC: a symlink planted in a shared dir can't make us empty
    another file, and an unreadable lock file makes us exit instead of crash.
    """
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    except OSError:
        return None
    handle = os.fdopen(fd, "r+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle

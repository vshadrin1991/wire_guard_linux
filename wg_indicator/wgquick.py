"""Runs `sudo -n wg-quick up|down <iface>` and turns the outcome into a user-facing Result."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Callable

from .tunnel import Action, validate_interface

# Absolute paths: the sudoers rule only matches these exact commands.
SUDO = "/usr/bin/sudo"
WG_QUICK = "/usr/bin/wg-quick"
SLOW_AFTER_SECONDS = 20.0

# `sudo -n` output when no NOPASSWD rule applies: classic sudo, then sudo-rs (Ubuntu 25.10+).
_NEEDS_PASSWORD = ("a password is required", "authentication is required")


@dataclass(frozen=True)
class Result:
    ok: bool
    message: str


def build_command(action: Action, interface: str) -> list[str]:
    if action not in ("up", "down"):
        raise ValueError(f"unknown action: {action!r}")
    return [SUDO, "-n", WG_QUICK, action, validate_interface(interface)]


def classify(action: Action, interface: str, returncode: int, stderr: str) -> Result:
    if returncode == 0:
        return Result(True, f"{interface} is {action}")
    if any(text in stderr for text in _NEEDS_PASSWORD):
        return Result(
            False,
            "sudo asked for a password. Run `sudo ./packaging/install.sh` "
            "to allow wg-quick without one.",
        )
    if action == "up" and "already exists" in stderr:
        return Result(True, f"{interface} was already up")
    if action == "down" and "is not a WireGuard interface" in stderr:
        return Result(True, f"{interface} was already down")
    # Skip "[#] ..." command-echo lines: on a failed `up` the last one is wg-quick's own
    # cleanup (`ip link delete dev wg0`), which would hide the real error.
    lines = [line for line in stderr.splitlines() if line.strip() and not line.startswith("[#]")]
    return Result(False, lines[-1] if lines else f"wg-quick exited with code {returncode}")


def _ignore(_message: str) -> None:
    return None


def run_action(
    action: Action,
    interface: str,
    *,
    popen=subprocess.Popen,
    slow_after: float = SLOW_AFTER_SECONDS,
    on_slow: Callable[[str], None] = _ignore,
) -> Result:
    """Blocks until wg-quick exits. Call it from a worker thread, never the GTK thread."""
    cmd = build_command(action, interface)
    try:
        proc = popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        return Result(False, f"could not start {cmd[0]}: {exc}")
    try:
        _, stderr = proc.communicate(timeout=slow_after)
    except subprocess.TimeoutExpired:
        on_slow(f"wg-quick {action} {interface} is still running after {slow_after:g}s…")
        # Never kill it: it runs as root (we may not be allowed to) and a half-finished
        # wg-quick leaves routes and DNS half-configured. Keep waiting instead.
        _, stderr = proc.communicate()
    return classify(action, interface, proc.returncode, stderr or "")

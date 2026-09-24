"""Is the WireGuard interface up? No GTK imports, so this is testable anywhere."""
from __future__ import annotations

import enum
import re
from pathlib import Path
from typing import Literal

Action = Literal["up", "down"]

SYS_NET_DIR = Path("/sys/class/net")
# Stricter than wg-quick's own rule: '=' and '+' would need escaping in sudoers.
_INTERFACE_RE = re.compile(r"[A-Za-z0-9_.-]{1,15}")


class TunnelState(enum.Enum):
    UP = "up"
    DOWN = "down"
    BUSY = "busy"


def validate_interface(name: str) -> str:
    if name in (".", "..") or not _INTERFACE_RE.fullmatch(name):
        raise ValueError(f"invalid WireGuard interface name: {name!r}")
    return name


def read_state(interface: str, sys_net_dir: Path = SYS_NET_DIR) -> TunnelState:
    """wg-quick up creates /sys/class/net/<iface> and wg-quick down removes it; no root needed."""
    return TunnelState.UP if (sys_net_dir / interface).exists() else TunnelState.DOWN


class Tunnel:
    """Live interface state plus a busy flag, so a second click can't start a second wg-quick."""

    def __init__(self, interface: str, sys_net_dir: Path = SYS_NET_DIR) -> None:
        self.interface = validate_interface(interface)
        self.sys_net_dir = sys_net_dir
        self.busy = False

    def current(self) -> TunnelState:
        if self.busy:
            return TunnelState.BUSY
        return read_state(self.interface, self.sys_net_dir)

    def begin_toggle(self) -> Action | None:
        """Pick the action for a click, or None if a wg-quick call is already running."""
        if self.busy:
            return None
        action: Action = "down" if self.current() is TunnelState.UP else "up"
        self.busy = True
        return action

    def finish(self) -> None:
        self.busy = False

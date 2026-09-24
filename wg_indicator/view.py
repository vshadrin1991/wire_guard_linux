"""What the top bar and menu show for each TunnelState."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .tunnel import TunnelState

ICON_DIR = Path(__file__).resolve().parent / "icons"
# Names without ".svg": AppIndicator looks them up in ICON_DIR.
ICON_UP = "wireguard-indicator-on"
ICON_DOWN = "wireguard-indicator-off"
ICON_BUSY = "wireguard-indicator-busy"
ICON_APP = "wireguard-indicator"


@dataclass(frozen=True)
class View:
    icon: str
    status_text: str
    toggle_label: str
    toggle_sensitive: bool


def view_for(state: TunnelState, interface: str) -> View:
    if state is TunnelState.UP:
        return View(ICON_UP, f"{interface}: connected", "Turn Off", True)
    if state is TunnelState.DOWN:
        return View(ICON_DOWN, f"{interface}: disconnected", "Turn On", True)
    return View(ICON_BUSY, f"{interface}: working…", "Working…", False)

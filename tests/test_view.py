import xml.etree.ElementTree as ET

import pytest

from wg_indicator.tunnel import TunnelState
from wg_indicator.view import ICON_APP, ICON_BUSY, ICON_DIR, ICON_DOWN, ICON_UP, View, view_for


def test_view_when_up():
    assert view_for(TunnelState.UP, "wg0") == View(ICON_UP, "wg0: connected", "Turn Off", True)


def test_view_when_down():
    assert view_for(TunnelState.DOWN, "wg0") == View(ICON_DOWN, "wg0: disconnected", "Turn On", True)


def test_view_when_busy_disables_toggle():
    assert view_for(TunnelState.BUSY, "wg0") == View(ICON_BUSY, "wg0: working…", "Working…", False)


@pytest.mark.parametrize("name", [ICON_UP, ICON_DOWN, ICON_BUSY, ICON_APP])
def test_icon_file_exists_and_is_svg(name):
    path = ICON_DIR / f"{name}.svg"
    assert path.is_file()
    assert ET.parse(path).getroot().tag == "{http://www.w3.org/2000/svg}svg"

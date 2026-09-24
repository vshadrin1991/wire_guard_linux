import pytest

from wg_indicator.tunnel import Tunnel, TunnelState, read_state, validate_interface


def test_read_state_is_up_when_interface_exists(tmp_path):
    (tmp_path / "wg0").mkdir()
    assert read_state("wg0", tmp_path) is TunnelState.UP


def test_read_state_is_down_when_interface_missing(tmp_path):
    assert read_state("wg0", tmp_path) is TunnelState.DOWN


def test_state_follows_changes_made_outside_the_app(tmp_path):
    tunnel = Tunnel("wg0", tmp_path)
    assert tunnel.current() is TunnelState.DOWN
    (tmp_path / "wg0").mkdir()  # someone ran `sudo wg-quick up wg0` in a terminal
    assert tunnel.current() is TunnelState.UP
    (tmp_path / "wg0").rmdir()  # ...and then `sudo wg-quick down wg0`
    assert tunnel.current() is TunnelState.DOWN


def test_begin_toggle_brings_a_down_tunnel_up(tmp_path):
    assert Tunnel("wg0", tmp_path).begin_toggle() == "up"


def test_begin_toggle_brings_an_up_tunnel_down(tmp_path):
    (tmp_path / "wg0").mkdir()
    assert Tunnel("wg0", tmp_path).begin_toggle() == "down"


def test_second_toggle_while_busy_is_ignored(tmp_path):
    tunnel = Tunnel("wg0", tmp_path)
    assert tunnel.begin_toggle() == "up"
    assert tunnel.current() is TunnelState.BUSY
    assert tunnel.begin_toggle() is None  # a second click must not start a second wg-quick
    tunnel.finish()
    assert tunnel.current() is TunnelState.DOWN
    assert tunnel.begin_toggle() == "up"


@pytest.mark.parametrize("name", ["wg0", "wg-office", "vpn_1", "wg.home", "x" * 15])
def test_validate_interface_accepts_real_names(name):
    assert validate_interface(name) == name


@pytest.mark.parametrize(
    "name",
    ["", ".", "..", "x" * 16, "wg0; reboot", "wg 0", "../etc", "wg=0", "wg0\n"],
)
def test_validate_interface_rejects_unsafe_names(name):
    with pytest.raises(ValueError):
        validate_interface(name)


def test_tunnel_rejects_unsafe_interface(tmp_path):
    with pytest.raises(ValueError):
        Tunnel("wg0; reboot", tmp_path)

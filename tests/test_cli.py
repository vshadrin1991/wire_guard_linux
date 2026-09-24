import pytest

from wg_indicator.__main__ import main, parse_args
from wg_indicator.instance import acquire_lock, lock_path


def test_default_interface_is_wg0():
    assert parse_args([]).interface == "wg0"


def test_custom_interface():
    assert parse_args(["--interface", "wg-office"]).interface == "wg-office"


def test_rejects_unsafe_interface(capsys):
    with pytest.raises(SystemExit) as exc:
        parse_args(["--interface", "wg0;reboot"])
    assert exc.value.code == 2
    assert "invalid WireGuard interface name" in capsys.readouterr().err


def test_second_lock_is_refused_until_first_is_released(tmp_path):
    path = tmp_path / "indicator.lock"
    first = acquire_lock(path)
    assert first is not None
    assert acquire_lock(path) is None
    first.close()
    again = acquire_lock(path)
    assert again is not None
    again.close()


def test_lock_path_prefers_xdg_runtime_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    path = lock_path("wg0")
    assert path.parent == tmp_path
    assert path.name.endswith("-wg0.lock")


def test_main_refuses_second_instance(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    held = acquire_lock(lock_path("wg0"))  # pretend the autostarted copy is running
    try:
        assert main(["--interface", "wg0"]) == 1
    finally:
        held.close()
    assert "already running" in capsys.readouterr().err

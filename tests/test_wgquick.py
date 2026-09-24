import subprocess

import pytest

from wg_indicator.wgquick import Result, build_command, classify, run_action


class FakeProc:
    """Stands in for subprocess.Popen's return value."""

    def __init__(self, returncode=0, stderr="", slow=False):
        self.returncode = returncode
        self.stderr_text = stderr
        self.slow = slow
        self.communicate_calls = 0
        self.killed = False

    def communicate(self, timeout=None):
        self.communicate_calls += 1
        if self.slow and self.communicate_calls == 1:
            raise subprocess.TimeoutExpired("sudo", timeout)
        return None, self.stderr_text

    def kill(self):
        self.killed = True


def popen_returning(proc, calls):
    def popen(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return proc

    return popen


def test_build_command_up():
    assert build_command("up", "wg0") == ["/usr/bin/sudo", "-n", "/usr/bin/wg-quick", "up", "wg0"]


def test_build_command_down():
    assert build_command("down", "wg0") == ["/usr/bin/sudo", "-n", "/usr/bin/wg-quick", "down", "wg0"]


@pytest.mark.parametrize("action", ["restart", "", "up; reboot"])
def test_build_command_rejects_unknown_action(action):
    with pytest.raises(ValueError):
        build_command(action, "wg0")


def test_build_command_rejects_unsafe_interface():
    with pytest.raises(ValueError):
        build_command("up", "wg0 && reboot")


def test_classify_success():
    assert classify("up", "wg0", 0, "[#] ip link add wg0 type wireguard\n").ok


@pytest.mark.parametrize(
    "stderr",
    [
        "sudo: a password is required\n",  # classic sudo (Ubuntu 22.04 / 24.04)
        "sudo-rs: interactive authentication is required\n",  # sudo-rs (Ubuntu 25.10+)
    ],
)
def test_classify_missing_sudoers_rule(stderr):
    result = classify("up", "wg0", 1, stderr)
    assert not result.ok
    assert "install.sh" in result.message


def test_classify_up_when_already_up_counts_as_success():
    assert classify("up", "wg0", 1, "wg-quick: `wg0' already exists\n").ok


def test_classify_down_when_already_down_counts_as_success():
    assert classify("down", "wg0", 1, "wg-quick: `wg0' is not a WireGuard interface\n").ok


def test_classify_already_exists_is_not_success_for_down():
    assert not classify("down", "wg0", 1, "wg-quick: `wg0' already exists\n").ok


def test_classify_reports_last_stderr_line():
    stderr = "[#] ip link add wg0 type wireguard\nwg-quick: `/etc/wireguard/wg0.conf' does not exist\n\n"
    assert classify("up", "wg0", 1, stderr) == Result(
        False, "wg-quick: `/etc/wireguard/wg0.conf' does not exist"
    )


def test_classify_skips_wg_quick_command_echo_lines():
    # A failed `up` cleans up after itself, so the last stderr line is `[#] ip link
    # delete dev wg0` — the real error is the last non-echo line.
    stderr = "[#] ip link add wg0 type wireguard\nwg-quick: resolvconf: command not found\n[#] ip link delete dev wg0\n"
    assert classify("up", "wg0", 1, stderr) == Result(False, "wg-quick: resolvconf: command not found")


def test_classify_empty_stderr_reports_exit_code():
    assert classify("up", "wg0", 3, "") == Result(False, "wg-quick exited with code 3")


def test_run_action_runs_sudo_wg_quick():
    calls = []
    result = run_action("up", "wg0", popen=popen_returning(FakeProc(), calls))
    assert result.ok
    cmd, kwargs = calls[0]
    assert cmd == ["/usr/bin/sudo", "-n", "/usr/bin/wg-quick", "up", "wg0"]
    assert kwargs["stdin"] is subprocess.DEVNULL  # sudo can never sit waiting for a password
    assert kwargs["stderr"] is subprocess.PIPE
    assert "shell" not in kwargs


def test_run_action_waits_for_slow_wg_quick_without_killing_it():
    proc = FakeProc(slow=True)
    slow_messages = []
    result = run_action(
        "up", "wg0", popen=popen_returning(proc, []), slow_after=0.01, on_slow=slow_messages.append
    )
    assert result.ok
    assert proc.killed is False
    assert proc.communicate_calls == 2
    assert len(slow_messages) == 1
    assert "wg0" in slow_messages[0]


def test_run_action_reports_missing_sudo():
    def popen(cmd, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", cmd[0])

    result = run_action("up", "wg0", popen=popen)
    assert not result.ok
    assert "could not start" in result.message

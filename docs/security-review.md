# Security review: WireGuard Indicator

| | |
|---|---|
| Date | 2026-09-24 |
| Commit reviewed | `4ad40a8` (Initial commit) |
| Scope | Every tracked file: `wg_indicator/*.py`, `packaging/install.sh`, `packaging/uninstall.sh`, `packaging/wireguard-indicator.desktop` |
| Method | Read all the code by hand, reproduced finding 3 locally, and checked `wg-quick` behaviour against the upstream `wireguard-tools` source (`src/wg-quick/linux.bash`) |

## Summary

Nothing critical or high-severity on a standard Ubuntu setup. The riskiest part, the passwordless sudo rule, is tightly scoped. Its real weak point is outside the code: whether only root can change the WireGuard config file. There are also a few low-severity fixes worth making.

| # | Severity | Finding | Where |
|---|---|---|---|
| 1 | Medium (depends on setup) | Security rests on who can edit `/etc/wireguard/wg0.conf` | [install.sh:22-23](../packaging/install.sh#L22), [install.sh:43](../packaging/install.sh#L43) |
| 2 | Design trade-off | Any program running as the user can switch the VPN off silently | [install.sh:43](../packaging/install.sh#L43) |
| 3 | Low | The launcher runs code from whatever folder it is started in | [install.sh:34](../packaging/install.sh#L34) |
| 4 | Low | The lock file falls back to `/tmp` and is opened unsafely | [instance.py:12](../wg_indicator/instance.py#L12), [instance.py:21](../wg_indicator/instance.py#L21) |
| 5 | Low | Uninstall kills too much | [uninstall.sh:7](../packaging/uninstall.sh#L7) |
| 6 | Low | Autostart runs for every user on the machine | [install.sh:50](../packaging/install.sh#L50) |
| 7 | Minor | `notify-send` can read an error message as an option | [app.py:92-99](../wg_indicator/app.py#L92) |
| 8 | Minor | Interface names may start with `-` | [tunnel.py:13](../wg_indicator/tunnel.py#L13), [install.sh:18](../packaging/install.sh#L18) |
| 9 | Minor | The `.desktop` file finds the launcher through `PATH` | [wireguard-indicator.desktop:5](../packaging/wireguard-indicator.desktop#L5) |

---

## Findings

### 1. Medium, depends on setup: security rests on who can edit `/etc/wireguard/wg0.conf`

**Problem.** The sudo rule at [install.sh:43](../packaging/install.sh#L43) lets anything logged in as the user run `wg-quick up wg0` and `wg-quick down wg0` as root, with no password. `wg-quick` runs the config's `PreUp`, `PostUp`, `PreDown` and `PostDown` lines as root shell commands (`eval`). It also follows symlinks to the config (`readlink -f`), and it only *warns* when the file is world-readable. It never refuses a file that others can write.

**Impact.** If the config, `/etc/wireguard`, or a symlink target is ever writable by the user or by a group other than root, any program running as the user gets root with no password prompt. Before this install, someone exploiting such a file would still have needed the user's sudo password.

**Fix.** [install.sh:22-23](../packaging/install.sh#L22) only warns when the config is missing. It should refuse to install unless the config exists and it and its folders belong to root:

```bash
CONF="/etc/wireguard/$IFACE.conf"
[[ -f "$CONF" ]] || die "$CONF does not exist; create it before installing"
REAL="$(readlink -f "$CONF")"
for p in "$REAL" "$(dirname "$REAL")" /etc/wireguard; do
  read -r owner mode < <(stat -c '%u %a' "$p")
  [[ $owner -eq 0 && $(( 8#$mode & 8#022 )) -eq 0 ]] \
    || die "$p must be owned by root and not writable by group or others"
done
```

Also add a line to the README: the passwordless rule is only as safe as the permissions on that config file.

### 2. Design trade-off: any program running as the user can switch the VPN off silently

**Problem.** The sudo rule covers every program running as the user, not just the indicator. Malware or any script can run `sudo -n /usr/bin/wg-quick down wg0` and nothing prompts. The only sign is the icon turning grey within 2 seconds.

**Impact.** If the VPN protects privacy or acts as a kill switch, a user-level compromise can now turn it off without a password.

**Options.**
- Keep `up` passwordless and make `down` ask for a password (for example through `pkexec` with a polkit `auth_admin_keep` action).
- Or accept the risk on purpose and write it down. The README's "Nothing else becomes passwordless" is true about *commands*, but it understates this.

### 3. Low: the launcher runs code from whatever folder it is started in (reproduced)

**Problem.** The launcher at [install.sh:34](../packaging/install.sh#L34) runs `python3 -m wg_indicator`. `python3 -m` puts the current folder at the front of `sys.path`, ahead of `PYTHONPATH` and the standard library. So a `wg_indicator/` package, or a file that shadows a standard module (`argparse.py`, `enum.py`, `tempfile.py` and so on), in the current folder runs instead of the installed code.

**Impact.** Running `wireguard-indicator &` (as the README suggests) inside an untrusted folder, such as a cloned repo or a download, runs that folder's code as the user. That code also gets the passwordless VPN toggle. Autostart starts in the home folder, so the usual path is safe.

**Reproduction.**

```bash
d=$(mktemp -d) && mkdir "$d/wg_indicator"
touch "$d/wg_indicator/__init__.py"
echo 'print("SHADOWED")' > "$d/wg_indicator/__main__.py"
cd "$d" && PYTHONPATH=/opt/wireguard-indicator /usr/bin/python3 -m wg_indicator
# prints SHADOWED instead of starting the indicator
```

**Fix.** Use isolated mode (`-I`, available in Python 3.10 on Ubuntu 22.04) and add the install folder to the path yourself. With this change, the current folder is no longer searched (verified):

```sh
exec /usr/bin/python3 -I -c 'import sys; sys.path.insert(0, "/opt/wireguard-indicator"); from wg_indicator.__main__ import main; sys.exit(main())' --interface "$IFACE" "$@"
```

### 4. Low: the lock file falls back to `/tmp` and is opened unsafely

**Problem.** When `XDG_RUNTIME_DIR` is not set, [instance.py:12](../wg_indicator/instance.py#L12) uses a predictable name in `/tmp`: `wireguard-indicator-<uid>-<iface>.lock`. [instance.py:21](../wg_indicator/instance.py#L21) opens it with `open(path, "w")`, which empties the file and follows symlinks.

**Impact.** Normal GNOME sessions always set `XDG_RUNTIME_DIR`, so this is an edge case. When it happens, another local user can:
- create the file first and hold the lock, so the indicator says "already running" and quits;
- create the file with a mode the user can't write, so the indicator crashes with `PermissionError`;
- point a symlink at one of the user's files so it gets emptied. Ubuntu's default `fs.protected_symlinks=1` blocks this, but the code shouldn't depend on it.

**Fix.** Fall back to a private folder for each user instead of `/tmp`, and open without emptying the file or following symlinks:

```python
def lock_path(interface: str) -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR")
    if not base:
        base = Path.home() / ".cache" / "wireguard-indicator"  # private, unlike /tmp
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
    return Path(base) / f"wireguard-indicator-{os.getuid()}-{interface}.lock"


def acquire_lock(path: Path) -> IO[str] | None:
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    handle = os.fdopen(fd, "r+")
    ...
```

### 5. Low: uninstall kills too much

**Problem.** [uninstall.sh:7](../packaging/uninstall.sh#L7) runs `pkill -f 'python3 -m wg_indicator'` as root. `-f` matches that text anywhere in any process's full command line, for every user.

**Impact.** It also kills unrelated processes whose command line contains that text, such as an editor, `grep` or `less` opened on it.

**Fix.** Anchor the pattern to the launcher's exact command, for example `pkill -f '^/usr/bin/python3 -m wg_indicator( |$)'`, or `'^/usr/bin/python3 -I -c .*wg_indicator'` after fix 3.

### 6. Low: autostart runs for every user on the machine

**Problem.** [install.sh:50](../packaging/install.sh#L50) installs the autostart entry into `/etc/xdg/autostart`, so the indicator starts for everyone who logs in. Only `$SUDO_USER` gets the sudo rule.

**Impact.** Other users see a VPN switch that usually fails. Other admins can still toggle the VPN while their sudo password is cached, because `sudo -n` accepts it. The switch's reach is wider than the rule suggests.

**Fix.** Install into `~$SUDO_USER/.config/autostart` (look up the home folder with `getent passwd "$SUDO_USER" | cut -d: -f6` and `chown` the file to the user), and remove it in `uninstall.sh`.

### 7. Minor: `notify-send` can read an error message as an option

**Problem.** [app.py:92-99](../wg_indicator/app.py#L92) passes the last line of `wg-quick`'s error output to `notify-send` as a plain argument. A line starting with `-` would be read as an option. That output comes from `wg-quick` and the config's hook commands, which only root controls, so the risk is low.

**Fix.** Put `"--"` before the title and message in the argument list.

### 8. Minor: interface names may start with `-`

**Problem.** Both the Python check ([tunnel.py:13](../wg_indicator/tunnel.py#L13)) and the bash check ([install.sh:18](../packaging/install.sh#L18)) accept names like `-h`. It's harmless today, because the sudo rule matches exact arguments and `wg-quick` with two arguments treats it as a name. But the launcher's `--interface -h` would break argparse.

**Fix.** Require the first character to be a letter, digit or underscore. This also rules out `.` and `..` without a special case, and it still accepts every name in the current tests:
- Python: `[A-Za-z0-9_][A-Za-z0-9_.-]{0,14}`
- bash: `^[A-Za-z0-9_][A-Za-z0-9_.-]{0,14}$`

### 9. Minor: the `.desktop` file finds the launcher through `PATH`

**Problem.** `Exec=wireguard-indicator` in [wireguard-indicator.desktop:5](../packaging/wireguard-indicator.desktop#L5) is found through `PATH`. Ubuntu's default `~/.profile` puts `~/.local/bin` ahead of `/usr/local/bin`. This only matters to something that can already write files as the user.

**Fix.** Use `Exec=/usr/local/bin/wireguard-indicator`.

---

## What's already solid

- **Tight sudo rule.** Exact arguments only, one user, one interface, run as root only. It is checked with `visudo -cf` before install, installed `0440 root:root`, and the file name avoids the "files with a `.` are silently ignored" trap.
- **Interface names are checked in both bash and Python.** The allowed characters exclude everything with special meaning in sudoers (`,` `:` `=` `\` `*` `?` `[` `]`). The bash check can't be fooled with a newline.
- **Safe command calls.** Commands are passed as lists with no shell, with absolute paths to `sudo` and `wg-quick`. `sudo -n` means the app never hangs on a password prompt.
- **`wg-quick` can't be redirected.** With exactly two arguments, it only accepts `up`, `down`, `save` or `strip` plus a name, and a name maps only to `/etc/wireguard/<name>.conf`. The sudo rule can't be bent into another config file or another command.
- **Reading the state needs no root.** The app checks for `/sys/class/net/<iface>`.
- **The app never kills `wg-quick`,** which runs as root. Killing it midway would leave routes and DNS half-configured.
- **No double runs.** The busy flag is only touched on the GTK main thread, so one click can't start a second `wg-quick`.

## Not security, but noticed

- **A failed "Turn On" shows the wrong message.** When `wg-quick up` fails after creating the interface, its cleanup (`trap 'del_if; exit' ... EXIT`) prints `[#] ip link delete dev wg0` last. [wgquick.py:44-45](../wg_indicator/wgquick.py#L44) shows the last line of error output, so the notification shows that cleanup line instead of the real error. Skip lines starting with `[#]` when choosing the message.
- **Installing for a second interface removes the first.** Running `install.sh wg1` overwrites the one sudo rule file (`/etc/sudoers.d/wireguard-indicator`) and the launcher, so `wg0` loses its passwordless rule without warning.
- **"Connected" means "the interface exists".** The green icon means `/sys/class/net/wg0` exists, not that the peers have completed a handshake. Checking handshakes needs root (`wg show`), so this is a known limit worth saying in the README.

## Suggested order of fixes

1. Finding 1: check the config's ownership in `install.sh` and document it.
2. Finding 3: `-I` launcher.
3. Finding 2: decide whether `down` should require a password, and write the decision down.
4. Findings 4, 5 and 6.
5. Minor findings 7, 8 and 9, and the wrong error message on a failed "Turn On".

# WireGuard Indicator

A top-bar icon for Ubuntu that turns a WireGuard tunnel on and off.

- **Turn On** runs `sudo wg-quick up wg0`
- **Turn Off** runs `sudo wg-quick down wg0`
- Icon: green shield = connected, grey = disconnected, amber = working.
- Middle-click the icon to toggle without opening the menu.
- Changes made elsewhere (terminal, systemd) show up within 2 seconds.

## Requirements

Ubuntu 22.04 or 24.04 (GNOME) with a working `/etc/wireguard/wg0.conf`.

```bash
sudo apt install wireguard-tools python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 libnotify-bin gnome-shell-extension-appindicator
```

The top-bar icon needs the **Ubuntu AppIndicators** GNOME extension, which Ubuntu enables by default. Check it:

```bash
gnome-extensions list --enabled | grep appindicator
```

## Install

```bash
sudo ./packaging/install.sh          # another interface: sudo ./packaging/install.sh wg1
wireguard-indicator &                # or log out and back in; it autostarts
```

The installer creates `/etc/sudoers.d/wireguard-indicator`. That rule lets **only your user** run **only** `wg-quick up wg0` and `wg-quick down wg0` without a password. Nothing else becomes passwordless.

## Uninstall

```bash
sudo ./packaging/uninstall.sh
```

## Development

Unit tests run anywhere, including macOS:

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install pytest
python3 -m pytest
```

To run the GUI from the repo on Ubuntu, use the system Python, because `gi` comes from apt:

```bash
/usr/bin/python3 -m wg_indicator --interface wg0
```

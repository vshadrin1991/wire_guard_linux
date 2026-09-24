#!/usr/bin/env bash
# Install WireGuard Indicator system-wide.
# Usage: sudo ./packaging/install.sh [interface]      (default interface: wg0)
set -euo pipefail

IFACE="${1:-wg0}"
PREFIX=/opt/wireguard-indicator
LAUNCHER=/usr/local/bin/wireguard-indicator
# No '.' in this name: sudo silently ignores /etc/sudoers.d files that contain one.
SUDOERS_FILE=/etc/sudoers.d/wireguard-indicator
WG_QUICK=/usr/bin/wg-quick
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

die() { echo "install.sh: $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "run with sudo: sudo $0 ${*:-}"
[[ -n "${SUDO_USER:-}" && "$SUDO_USER" != root ]] || die "run via sudo from your own (non-root) account"
[[ "$IFACE" =~ ^[A-Za-z0-9_.-]{1,15}$ && "$IFACE" != . && "$IFACE" != .. ]] || die "invalid interface name: $IFACE"
[[ -x "$WG_QUICK" ]] || die "$WG_QUICK not found. Install it: sudo apt install wireguard-tools"
/usr/bin/python3 -c 'import gi; gi.require_version("Gtk", "3.0"); gi.require_version("AyatanaAppIndicator3", "0.1")' 2>/dev/null \
  || die "GTK/AppIndicator bindings missing. Install them: sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 libnotify-bin"
[[ -f "/etc/wireguard/$IFACE.conf" ]] \
  || echo "install.sh: warning: /etc/wireguard/$IFACE.conf does not exist yet; Turn On will fail until it does" >&2

echo "==> Installing app to $PREFIX"
install -d -m 0755 "$PREFIX/wg_indicator/icons"
install -m 0644 "$SRC"/wg_indicator/*.py "$PREFIX/wg_indicator/"
install -m 0644 "$SRC"/wg_indicator/icons/*.svg "$PREFIX/wg_indicator/icons/"

echo "==> Installing launcher $LAUNCHER"
cat > "$LAUNCHER" <<EOF
#!/bin/sh
# System python3 on purpose: PyGObject comes from apt, not pip.
PYTHONPATH="$PREFIX" exec /usr/bin/python3 -m wg_indicator --interface "$IFACE" "\$@"
EOF
chmod 0755 "$LAUNCHER"

echo "==> Allowing $SUDO_USER to run 'wg-quick up/down $IFACE' without a password"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
cat > "$TMP" <<EOF
# Installed by wireguard-indicator. Remove with: sudo ./packaging/uninstall.sh
$SUDO_USER ALL=(root) NOPASSWD: $WG_QUICK up $IFACE, $WG_QUICK down $IFACE
EOF
visudo -cf "$TMP" >/dev/null || die "generated sudoers rule failed validation; /etc/sudoers.d left untouched"
install -m 0440 -o root -g root "$TMP" "$SUDOERS_FILE"

echo "==> Adding app-grid entry and autostart"
install -m 0644 "$SRC/packaging/wireguard-indicator.desktop" /usr/share/applications/wireguard-indicator.desktop
install -m 0644 "$SRC/packaging/wireguard-indicator.desktop" /etc/xdg/autostart/wireguard-indicator.desktop

echo "Done. Start it now with:  wireguard-indicator &   (it also starts automatically at login)"

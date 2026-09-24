#!/usr/bin/env bash
# Remove everything install.sh added. Leaves /etc/wireguard and the tunnel's current state alone.
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "uninstall.sh: run with sudo: sudo $0" >&2; exit 1; }

# Anchored to the exact launcher command so unrelated processes containing the text
# (an editor, grep, less) aren't killed.
pkill -f '^/usr/bin/python3 -I -c .*wg_indicator' || true
rm -f /etc/sudoers.d/wireguard-indicator \
      /usr/local/bin/wireguard-indicator \
      /usr/share/applications/wireguard-indicator.desktop \
      /etc/xdg/autostart/wireguard-indicator.desktop  # from versions that autostarted for all users

if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != root ]]; then
  USER_HOME="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
  [[ -n "$USER_HOME" ]] && rm -f "$USER_HOME/.config/autostart/wireguard-indicator.desktop"
fi
rm -rf /opt/wireguard-indicator

echo "Uninstalled. Your WireGuard config and tunnel state were left as they are."

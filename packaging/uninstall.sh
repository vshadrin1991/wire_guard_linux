#!/usr/bin/env bash
# Remove everything install.sh added. Leaves /etc/wireguard and the tunnel's current state alone.
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "uninstall.sh: run with sudo: sudo $0" >&2; exit 1; }

pkill -f 'python3 -m wg_indicator' || true
rm -f /etc/sudoers.d/wireguard-indicator \
      /usr/local/bin/wireguard-indicator \
      /usr/share/applications/wireguard-indicator.desktop \
      /etc/xdg/autostart/wireguard-indicator.desktop
rm -rf /opt/wireguard-indicator

echo "Uninstalled. Your WireGuard config and tunnel state were left as they are."

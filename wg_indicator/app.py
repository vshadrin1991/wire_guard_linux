"""GTK 3 + Ayatana AppIndicator front-end. Needs an Ubuntu desktop session; checked by hand."""
from __future__ import annotations

import signal
import threading

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3 as AppIndicator  # noqa: E402
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from .tunnel import Action, Tunnel  # noqa: E402
from .view import ICON_APP, ICON_DIR, ICON_DOWN, View, view_for  # noqa: E402
from .wgquick import Result, run_action  # noqa: E402

POLL_SECONDS = 2


class IndicatorApp:
    def __init__(self, interface: str) -> None:
        self.interface = interface
        self.tunnel = Tunnel(interface)
        self._shown: View | None = None

        self.indicator = AppIndicator.Indicator.new_with_path(
            f"wireguard-indicator-{interface}",
            ICON_DOWN,
            AppIndicator.IndicatorCategory.SYSTEM_SERVICES,
            str(ICON_DIR),
        )
        self.indicator.set_title(f"WireGuard {interface}")
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)

        self.status_item = Gtk.MenuItem(label="")
        self.status_item.set_sensitive(False)  # read-only status line
        self.toggle_item = Gtk.MenuItem(label="")
        self.toggle_item.connect("activate", self.on_toggle)
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda _item: Gtk.main_quit())

        menu = Gtk.Menu()
        for item in (self.status_item, self.toggle_item, Gtk.SeparatorMenuItem(), quit_item):
            menu.append(item)
        menu.show_all()
        self.indicator.set_menu(menu)
        self.indicator.set_secondary_activate_target(self.toggle_item)  # middle-click toggles

        self.refresh()
        GLib.timeout_add_seconds(POLL_SECONDS, self._poll)

    def refresh(self) -> None:
        view = view_for(self.tunnel.current(), self.interface)
        if view == self._shown:  # avoid a D-Bus icon update every poll
            return
        self._shown = view
        self.indicator.set_icon_full(view.icon, view.status_text)
        self.status_item.set_label(view.status_text)
        self.toggle_item.set_label(view.toggle_label)
        self.toggle_item.set_sensitive(view.toggle_sensitive)

    def _poll(self) -> bool:
        self.refresh()
        return GLib.SOURCE_CONTINUE

    def on_toggle(self, _item: Gtk.MenuItem) -> None:
        action = self.tunnel.begin_toggle()
        if action is None:  # a wg-quick call is already running
            return
        self.refresh()
        threading.Thread(target=self._run_in_background, args=(action,), daemon=True).start()

    def _run_in_background(self, action: Action) -> None:
        result = run_action(
            action,
            self.interface,
            on_slow=lambda message: GLib.idle_add(notify, self.interface, message),
        )
        GLib.idle_add(self._on_finished, result)  # back to the GTK main thread

    def _on_finished(self, result: Result) -> bool:
        self.tunnel.finish()
        self.refresh()  # the icon comes from sysfs, not from result.ok
        if not result.ok:
            notify(self.interface, result.message)
        return GLib.SOURCE_REMOVE


def notify(interface: str, message: str) -> None:
    try:
        Gio.Subprocess.new(
            [
                "notify-send",
                "--app-name=WireGuard Indicator",
                f"--icon={ICON_DIR / (ICON_APP + '.svg')}",
                "--",  # wg-quick's stderr goes in `message`; a leading '-' must not become an option
                f"WireGuard {interface}",
                message,
            ],
            Gio.SubprocessFlags.NONE,
        )
    except GLib.Error:
        pass  # notify-send missing; the menu's status line still shows the real state


def run(interface: str) -> None:
    IndicatorApp(interface)
    for sig in (signal.SIGINT, signal.SIGTERM):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, Gtk.main_quit)
    Gtk.main()

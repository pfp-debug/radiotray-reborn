import logging
from typing import TYPE_CHECKING

from gi.repository import Gtk, GLib

from radiotray.plugins.base import Plugin
from radiotray.events.manager import EventManager

if TYPE_CHECKING:
    from radiotray.config.bookmarks import BookmarkManager
    from radiotray.config.settings import SettingsManager
    from radiotray.core.mediator import StateMediator


class SleepTimerPlugin(Plugin):
    name = "Sleep Timer"
    description = "Automatically stop playback after a specified time"
    author = "RadioTray Contributors"
    version = "1.0"

    TIMER_OPTIONS = [
        (15, "15 minutes"),
        (30, "30 minutes"),
        (45, "45 minutes"),
        (60, "1 hour"),
        (90, "1.5 hours"),
        (120, "2 hours"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._timeout_id: int | None = None
        self._remaining_seconds: int = 0
        self._timer_label: str = ""
        self._menu_item: Gtk.MenuItem | None = None
        self._update_source_id: int | None = None

    def activate(self) -> None:
        self._active = True
        self.logger.info("Sleep Timer plugin activated")

    def deactivate(self) -> None:
        self._cancel_timer()
        self._active = False
        self.logger.info("Sleep Timer plugin deactivated")

    def get_menu_item(self) -> Gtk.MenuItem:
        if self._menu_item is None:
            self._menu_item = Gtk.MenuItem(label=self.name)
            submenu = Gtk.Menu()

            for minutes, label in self.TIMER_OPTIONS:
                item = Gtk.MenuItem(label=label)
                item.connect("activate", lambda _, m=minutes: self._set_timer(m))
                submenu.append(item)

            submenu.append(Gtk.SeparatorMenuItem())

            custom_item = Gtk.MenuItem(label="Custom...")
            custom_item.connect("activate", lambda _: self._show_custom_dialog())
            submenu.append(custom_item)

            submenu.append(Gtk.SeparatorMenuItem())

            self._cancel_item = Gtk.MenuItem(label="Cancel Timer")
            self._cancel_item.connect("activate", lambda _: self.cancel_timer())
            self._cancel_item.set_sensitive(False)
            submenu.append(self._cancel_item)

            self._menu_item.set_submenu(submenu)

        self._update_menu_item()
        return self._menu_item

    def _show_custom_dialog(self) -> None:
        dialog = Gtk.Dialog(
            title="Custom Sleep Timer",
            flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Start", Gtk.ResponseType.OK)
        dialog.set_default_size(300, 150)

        content = dialog.get_content_area()
        content.set_spacing(10)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox.set_homogeneous(False)

        label = Gtk.Label(label="Stop after:")
        hbox.pack_start(label, False, False, 0)

        self._custom_spin = Gtk.SpinButton()
        self._custom_spin.set_range(1, 1440)
        self._custom_spin.set_value(30)
        self._custom_spin.set_increments(1, 5)
        hbox.pack_start(self._custom_spin, True, True, 0)

        label_min = Gtk.Label(label="minutes")
        hbox.pack_start(label_min, False, False, 0)

        content.pack_start(hbox, False, False, 0)

        dialog.show_all()
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            minutes = int(self._custom_spin.get_value())
            self._set_timer(minutes)

        dialog.destroy()

    def _update_menu_item(self) -> None:
        if self._menu_item is not None:
            if self._remaining_seconds > 0:
                self._menu_item.set_label(f"Sleep Timer ({self._timer_label})")
            else:
                self._menu_item.set_label(self.name)

        if hasattr(self, "_cancel_item"):
            self._cancel_item.set_sensitive(self._remaining_seconds > 0)

    def _set_timer(self, minutes: int) -> None:
        self._cancel_timer()
        self._remaining_seconds = minutes * 60

        from gi.repository import GLib

        self._timeout_id = GLib.timeout_add(1000, self._update_countdown)

        self.logger.info(f"Sleep timer set for {minutes} minutes")
        self._update_menu_item()

    def cancel_timer(self) -> None:
        self._cancel_timer()
        self._update_menu_item()

    def _cancel_timer(self) -> None:
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

        if self._update_source_id is not None:
            GLib.source_remove(self._update_source_id)
            self._update_source_id = None

        self._remaining_seconds = 0
        self._timer_label = ""
        self.logger.info("Sleep timer cancelled")

    def _update_countdown(self) -> bool:
        if self._remaining_seconds > 0:
            self._remaining_seconds -= 1
            self._update_timer_label()
            self._update_menu_item()

            if self._remaining_seconds == 0:
                self._on_timeout()
                return False
            return True
        return False

    def _update_timer_label(self) -> None:
        hours = self._remaining_seconds // 3600
        minutes = (self._remaining_seconds % 3600) // 60
        seconds = self._remaining_seconds % 60

        if hours > 0:
            self._timer_label = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            self._timer_label = f"{minutes}:{seconds:02d}"

    def get_tooltip_text(self) -> str | None:
        if self._remaining_seconds > 0:
            return f"Sleep in {self._timer_label}"
        return None

    def _on_timeout(self) -> None:
        self.logger.info("Sleep timer expired, stopping playback")
        if self.mediator:
            self.mediator.stop()
        self._timeout_id = None
        self._remaining_seconds = 0
        self._timer_label = ""
        self._update_menu_item()

import logging
import random
from typing import TYPE_CHECKING

from gi.repository import Gtk

from radiotray.plugins.base import Plugin
from radiotray.events.manager import EventManager

if TYPE_CHECKING:
    from radiotray.config.bookmarks import BookmarkManager
    from radiotray.config.settings import SettingsManager
    from radiotray.core.mediator import StateMediator


class StationSwitcherPlugin(Plugin):
    name = "Station Switcher"
    description = "Switch between stations using Next/Previous"
    author = "RadioTray Contributors"
    version = "1.0"

    def __init__(self) -> None:
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._stations: list[str] = []
        self._current_index: int = -1
        self._random_mode: bool = False
        self._menu_item: Gtk.MenuItem | None = None

    def activate(self) -> None:
        self._active = True
        self._load_stations()
        self.logger.info("Station Switcher plugin activated")

    def deactivate(self) -> None:
        self._active = False
        self.logger.info("Station Switcher plugin deactivated")

    def _load_stations(self) -> None:
        self._stations = []
        if self.bookmarks:
            self.bookmarks.walk_bookmarks(
                lambda name, _: self._stations.append(name) if name != "root" else None,
                lambda name, _: self._stations.append(name),
                None,
            )
        self.logger.debug(f"Loaded {len(self._stations)} stations")

    def _on_bookmarks_changed(self, data: dict) -> None:
        self._load_stations()

    def get_menu_item(self) -> Gtk.MenuItem:
        if self._menu_item is None:
            self._menu_item = Gtk.MenuItem(label=self.name)
            submenu = Gtk.Menu()

            self._prev_item = Gtk.MenuItem(label="Previous Station")
            self._prev_item.connect("activate", lambda _: self._play_previous())
            submenu.append(self._prev_item)

            self._next_item = Gtk.MenuItem(label="Next Station")
            self._next_item.connect("activate", lambda _: self._play_next())
            submenu.append(self._next_item)

            submenu.append(Gtk.SeparatorMenuItem())

            self._random_item = Gtk.CheckMenuItem(label="Random Mode")
            self._random_item.set_active(self._random_mode)
            self._random_item.connect("toggled", self._on_random_toggled)
            submenu.append(self._random_item)

            self._menu_item.set_submenu(submenu)

        return self._menu_item

    def _on_random_toggled(self, item: Gtk.CheckMenuItem) -> None:
        self._random_mode = item.get_active()
        self.logger.info(f"Random mode: {self._random_mode}")

    def _get_current_station(self) -> str | None:
        if self.mediator:
            return self.mediator.context.station
        return None

    def _play_next(self) -> None:
        if not self._stations:
            return

        current = self._get_current_station()

        if self._random_mode:
            new_station = random.choice(self._stations)
            if new_station != current:
                self._play_station(new_station)
                return

        if current is None:
            self._play_station(self._stations[0])
            return

        try:
            idx = self._stations.index(current)
            idx = (idx + 1) % len(self._stations)
            self._play_station(self._stations[idx])
        except ValueError:
            self._play_station(self._stations[0])

    def _play_previous(self) -> None:
        if not self._stations:
            return

        current = self._get_current_station()

        if self._random_mode:
            new_station = random.choice(self._stations)
            if new_station != current:
                self._play_station(new_station)
                return

        if current is None:
            self._play_station(self._stations[-1])
            return

        try:
            idx = self._stations.index(current)
            idx = (idx - 1) % len(self._stations)
            self._play_station(self._stations[idx])
        except ValueError:
            self._play_station(self._stations[-1])

    def _play_station(self, station: str) -> None:
        if self.mediator:
            self.logger.info(f"Switching to: {station}")
            self.mediator.play(station)

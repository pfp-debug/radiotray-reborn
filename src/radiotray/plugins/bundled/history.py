import logging
from typing import TYPE_CHECKING, NamedTuple
from collections import deque

from gi.repository import Gtk

from radiotray.plugins.base import Plugin
from radiotray.events.manager import EventManager

if TYPE_CHECKING:
    from radiotray.config.bookmarks import BookmarkManager
    from radiotray.config.settings import SettingsManager
    from radiotray.core.mediator import StateMediator


class HistoryEntry(NamedTuple):
    station: str
    track: str = ""
    artist: str = ""

    def display(self) -> str:
        if self.artist and self.track:
            return f"{self.station} - {self.artist} - {self.track}"
        elif self.track:
            return f"{self.station} - {self.track}"
        else:
            return self.station


class HistoryPlugin(Plugin):
    name = "History"
    description = "Keep track of recently played stations"
    author = "RadioTray Contributors"
    version = "1.0"

    MAX_HISTORY = 50

    def __init__(self) -> None:
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._history: deque[HistoryEntry] = deque(maxlen=self.MAX_HISTORY)
        self._menu_item: Gtk.MenuItem | None = None
        self._current_station: str = ""
        self._current_track: str = ""
        self._current_artist: str = ""

    def activate(self) -> None:
        if self.event_manager:
            self.event_manager.subscribe(EventManager.STATE_CHANGED, self._on_state_changed)
            self.event_manager.subscribe(EventManager.SONG_CHANGED, self._on_song_changed)
        self._active = True
        self.logger.info("History plugin activated")

    def deactivate(self) -> None:
        if self.event_manager:
            self.event_manager.unsubscribe(EventManager.STATE_CHANGED, self._on_state_changed)
            self.event_manager.unsubscribe(EventManager.SONG_CHANGED, self._on_song_changed)
        self._active = False
        self.logger.info("History plugin deactivated")

    def get_menu_item(self) -> Gtk.MenuItem:
        if self._menu_item is None:
            self._menu_item = Gtk.MenuItem(label=self.name)
            self._menu_item.connect("activate", lambda _: self._show_history_dialog())
        return self._menu_item

    def _on_state_changed(self, data: dict) -> None:
        state = data.get("state", "")
        station = data.get("station", "")

        if state == "playing" and station:
            self._current_station = station
            self._add_to_history()

    def _on_song_changed(self, data: dict) -> None:
        self._current_track = data.get("title", "")
        self._current_artist = data.get("artist", "")

        if self._current_station and self._history:
            last = self._history[-1]
            if last.station == self._current_station:
                self._history[-1] = HistoryEntry(
                    station=self._current_station,
                    track=self._current_track,
                    artist=self._current_artist,
                )
                self.logger.debug(f"Updated history with track: {last.display()}")

    def _add_to_history(self) -> None:
        entry = HistoryEntry(
            station=self._current_station,
            track=self._current_track,
            artist=self._current_artist,
        )

        for i, existing in enumerate(self._history):
            if existing.station == entry.station:
                self._history.remove(existing)
                break

        self._history.append(entry)
        self.logger.debug(f"Added to history: {entry.display()}")

    def get_history(self) -> list[HistoryEntry]:
        return list(reversed(self._history))

    def clear_history(self) -> None:
        self._history.clear()

    def _show_history_dialog(self) -> None:
        dialog = Gtk.Dialog(
            title=self.name,
            flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
        )
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(500, 500)

        content = dialog.get_content_area()
        content.set_spacing(10)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)

        store = Gtk.ListStore(str, str)
        for entry in self.get_history():
            station = entry.station
            if entry.artist or entry.track:
                info = f"{entry.artist} - {entry.track}" if entry.artist else entry.track
                station = f"{entry.station}  |  {info}"
            store.append([entry.station, station])

        tree = Gtk.TreeView(model=store)
        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn("Station / Track Info", renderer, text=1)
        tree.append_column(col)
        tree.connect("row-activated", self._on_station_activated)

        scroll.add(tree)
        content.pack_start(scroll, True, True, 0)

        btn_box = Gtk.ButtonBox(orientation=Gtk.Orientation.HORIZONTAL)
        btn_box.set_layout(Gtk.ButtonBoxStyle.END)

        clear_btn = Gtk.Button(label="Clear History")
        clear_btn.connect("clicked", lambda _: self._clear_and_refresh(store))
        btn_box.pack_start(clear_btn, False, False, 0)

        content.pack_start(btn_box, False, False, 0)

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def _clear_and_refresh(self, store: Gtk.ListStore) -> None:
        self.clear_history()
        store.clear()

    def _on_station_activated(
        self, tree: Gtk.TreeView, path: Gtk.TreePath, column: Gtk.TreeViewColumn
    ) -> None:
        model = tree.get_model()
        station = model[path][0]
        if self.mediator:
            self.mediator.play(station)

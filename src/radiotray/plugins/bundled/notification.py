import logging
from typing import TYPE_CHECKING

from gi.repository import Notify, GdkPixbuf

from radiotray.plugins.base import Plugin
from radiotray.constants import APP_NAME, APP_ICON
from radiotray.events.manager import EventManager

if TYPE_CHECKING:
    from radiotray.config.bookmarks import BookmarkManager
    from radiotray.config.settings import SettingsManager
    from radiotray.core.mediator import StateMediator


class NotificationPlugin(Plugin):
    name = "Notification"
    description = "Desktop notifications for track changes"
    author = "RadioTray Contributors"
    version = "1.0"

    def __init__(self) -> None:
        super().__init__()
        self.logger = logging.getLogger("radiotray.plugins.notification")
        self.logger.setLevel(logging.DEBUG)
        root = logging.getLogger("radiotray")
        if root.handlers and not self.logger.handlers:
            for h in root.handlers:
                self.logger.addHandler(h)
        self._notification: Notify.Notification | None = None
        self._last_station: str = ""
        self._last_title: str = ""
        self._last_artist: str = ""
        self._last_message: str | None = None

    def activate(self) -> None:
        Notify.init(APP_NAME)
        if self.event_manager:
            self.event_manager.subscribe(EventManager.STATE_CHANGED, self._on_state_changed)
            self.event_manager.subscribe(EventManager.SONG_CHANGED, self._on_song_changed)
            self.event_manager.subscribe(EventManager.STATION_ERROR, self._on_error)
        self._active = True
        self.logger.info("Notification plugin activated")

    def deactivate(self) -> None:
        if self.event_manager:
            self.event_manager.unsubscribe(EventManager.STATE_CHANGED, self._on_state_changed)
            self.event_manager.unsubscribe(EventManager.SONG_CHANGED, self._on_song_changed)
            self.event_manager.unsubscribe(EventManager.STATION_ERROR, self._on_error)
        self._active = False
        self.logger.info("Notification plugin deactivated")

    def _show_notification(self, title: str, message: str) -> None:
        if message == self._last_message and title == self._last_station:
            return

        self._last_message = message
        self._last_station = title

        try:
            if self._notification is None:
                self._notification = Notify.Notification.new(title, message, None)
            else:
                self._notification.update(title, message, None)

            if APP_ICON.exists():
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(str(APP_ICON), 48, 48)
                    self._notification.set_icon_from_pixbuf(pixbuf)
                except Exception:
                    pass

            self._notification.set_urgency(Notify.Urgency.LOW)
            self._notification.show()
        except Exception as e:
            self.logger.error(f"Failed to show notification: {e}")

    def _on_state_changed(self, data: dict) -> None:
        state = data.get("state", "")
        station = data.get("station", "")

        if state == "playing":
            self._last_station = station
            if self._last_title or self._last_artist:
                message = self._format_track_info()
                self._show_notification(f"Now Playing: {station}", message)
            else:
                self._show_notification("Now Playing", station)
        elif state == "stopped":
            self._last_station = ""
            self._last_title = ""
            self._last_artist = ""
            self._last_message = None

    def _on_song_changed(self, data: dict) -> None:
        self.logger.info("=== NOTIFICATION PLUGIN: _on_song_changed ENTERED ===")
        title = data.get("title", "")
        artist = data.get("artist", "")
        station = data.get("station", self._last_station)

        self.logger.info(
            f"Notification: SONG_CHANGED received - title: {title}, artist: {artist}, station: {station}"
        )

        if not title and not artist:
            return

        self._last_title = title
        self._last_artist = artist

        message = self._format_track_info()
        self.logger.info(f"Notification: Showing - {station}: {message}")
        if station:
            self._show_notification(f"Now Playing: {station}", message)
        else:
            self._show_notification("Now Playing", message)

    def _format_track_info(self) -> str:
        if self._last_artist and self._last_title:
            return f"{self._last_artist} - {self._last_title}"
        elif self._last_title:
            return self._last_title
        elif self._last_artist:
            return self._last_artist
        return ""

    def _on_error(self, data: dict) -> None:
        error = data.get("error", "Unknown error")
        self._show_notification("Radio Tray Error", error)

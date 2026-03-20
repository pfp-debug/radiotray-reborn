import logging
from typing import TYPE_CHECKING

from radiotray.models.context import Context, PlaybackState
from radiotray.events.manager import EventManager

if TYPE_CHECKING:
    from radiotray.config.bookmarks import BookmarkManager
    from radiotray.config.settings import SettingsManager
    from radiotray.core.player import GStreamerPlayer


class StateMediator:
    UNKNOWN_RADIO = "Unknown Radio"

    def __init__(
        self,
        bookmarks: "BookmarkManager",
        settings: "SettingsManager",
        event_manager: EventManager,
    ) -> None:
        self.bookmarks = bookmarks
        self.settings = settings
        self.event_manager = event_manager
        self.context = Context()
        self.context.state = PlaybackState.STOPPED
        self.player: "GStreamerPlayer | None" = None
        self.logger = logging.getLogger(__name__)

        last_station = settings.get_last_station()
        self.context.station = last_station or ""
        self.context.volume = settings.get_volume()

        if last_station and not bookmarks.get_radio_url(last_station):
            self.context.station = ""

    def set_player(self, player: "GStreamerPlayer") -> None:
        self.player = player
        self.player.set_volume(self.context.volume)
        self.event_manager.subscribe(EventManager.STATE_CHANGED, self.on_state_changed)
        self.event_manager.subscribe(EventManager.SONG_CHANGED, self.on_song_changed)

    def play(self, station: str) -> None:
        self.logger.info(f"Play request: {station}")

        if self.player:
            self.player.stop()
            self.context.state = PlaybackState.STOPPED

        url = self.bookmarks.get_radio_url(station)
        self.logger.info(f"Station '{station}' URL: {url}")
        if url:
            self.context.station = station
            self.context.reset_song_info()
            self.context.state = PlaybackState.CONNECTING
            self.event_manager.notify(
                EventManager.STATE_CHANGED, {"state": "connecting", "station": station}
            )
            self.player.start(url)
            self.settings.set_last_station(station)
        else:
            self.logger.error(f"Station not found: {station}")
            self.context.station = ""
            self.player.stop()

    def play_url(self, url: str) -> None:
        self.logger.debug(f"Play URL: {url}")
        if self.is_playing() and self.player:
            self.player.stop()

        self.context.station = self.UNKNOWN_RADIO
        self.context.reset_song_info()
        self.event_manager.notify(
            EventManager.STATE_CHANGED, {"state": "connecting", "station": self.UNKNOWN_RADIO}
        )
        if self.player:
            self.player.start(url)

    def play_last(self) -> None:
        if self.context.station:
            self.play(self.context.station)

    def stop(self) -> None:
        self.logger.info("Stop request")
        if self.player:
            self.player.stop()
        self.context.state = PlaybackState.STOPPED
        self.event_manager.notify(
            EventManager.STATE_CHANGED, {"state": "stopped", "station": self.context.station}
        )

    def is_playing(self) -> bool:
        return self.context.state == PlaybackState.PLAYING

    def volume_up(self) -> None:
        if self.player:
            self.player.volume_up()
        self.event_manager.notify(EventManager.VOLUME_CHANGED, {"volume": self.get_volume()})

    def volume_down(self) -> None:
        if self.player:
            self.player.volume_down()
        self.event_manager.notify(EventManager.VOLUME_CHANGED, {"volume": self.get_volume()})

    def set_volume(self, volume: float) -> None:
        if self.player:
            self.player.set_volume(volume)
        self.event_manager.notify(EventManager.VOLUME_CHANGED, {"volume": self.get_volume()})

    def get_volume(self) -> int:
        return self.context.get_volume_percent()

    def update_volume(self, volume: float) -> None:
        self.context.volume = volume
        self.settings.set_volume(round(volume, 2))

    def on_state_changed(self, data: dict) -> None:
        state_str = data.get("state", "stopped")
        self.context.state = PlaybackState(state_str)
        self.logger.debug(f"State: {self.context.state}")

    def on_song_changed(self, data: dict) -> None:
        if "artist" in data:
            self.context.artist = data["artist"]
        if "title" in data:
            self.context.title = data["title"]

    def get_context(self) -> Context:
        return self.context

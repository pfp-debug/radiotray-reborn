import logging
import threading
from typing import TYPE_CHECKING

from radiotray.plugins.base import Plugin
from radiotray.events.manager import EventManager
from radiotray.constants import APP_NAME

if TYPE_CHECKING:
    from radiotray.config.bookmarks import BookmarkManager
    from radiotray.config.settings import SettingsManager
    from radiotray.core.mediator import StateMediator

try:
    import dbus
    import dbus.service

    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False


class MprisPlugin(Plugin):
    name = "MPRIS"
    description = "MPRIS2 interface for external media player control"
    author = "RadioTray Contributors"
    version = "1.0"

    BUS_NAME = "org.mpris.MediaPlayer2.radiotray"
    OBJECT_PATH = "/org/mpris/MediaPlayer2"

    def __init__(self) -> None:
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._bus = None
        self._mpris_object = None
        self._current_station = ""
        self._current_title = ""
        self._current_artist = ""
        self._playback_status = "Stopped"

    def activate(self) -> None:
        if not DBUS_AVAILABLE:
            self.logger.warning("MPRIS plugin requires python-dbus")
            return

        self._active = True

        if self.event_manager:
            self.event_manager.subscribe(EventManager.STATE_CHANGED, self._on_state_changed)
            self.event_manager.subscribe(EventManager.SONG_CHANGED, self._on_song_changed)

        self._start_dbus()
        self.logger.info("MPRIS plugin activated")

    def deactivate(self) -> None:
        self._active = False

        if self.event_manager:
            self.event_manager.unsubscribe(EventManager.STATE_CHANGED, self._on_state_changed)
            self.event_manager.unsubscribe(EventManager.SONG_CHANGED, self._on_song_changed)

        self._stop_dbus()
        self.logger.info("MPRIS plugin deactivated")

    def _start_dbus(self) -> None:
        try:
            import dbus.mainloop.glib
            from gi.repository import GLib

            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

            self._bus = dbus.service.BusName(
                self.BUS_NAME, bus=dbus.SessionBus(), do_not_queue=True
            )

            self._mpris_object = MprisObject(self._bus, self.OBJECT_PATH, self)

            self.logger.info("MPRIS interface registered")
        except Exception as e:
            self.logger.warning(f"Failed to start MPRIS: {e}")
            self._bus = None
            self._mpris_object = None

    def _stop_dbus(self) -> None:
        try:
            if self._bus:
                self._bus.release()
                self._bus = None
                self._mpris_object = None
        except Exception:
            pass

    def _on_state_changed(self, data: dict) -> None:
        state = data.get("state", "")
        station = data.get("station", "")

        self._current_station = station

        if state == "playing":
            self._playback_status = "Playing"
        elif state == "connecting":
            self._playback_status = "Playing"
        else:
            self._playback_status = "Stopped"

        if self._mpris_object:
            self._mpris_object.update_status(self._playback_status, self._current_station)

    def _on_song_changed(self, data: dict) -> None:
        self._current_title = data.get("title", "")
        self._current_artist = data.get("artist", "")

        if self._mpris_object:
            self._mpris_object.update_metadata(
                self._current_station, self._current_artist, self._current_title
            )

    def play(self) -> None:
        if self.mediator and self.mediator.context.station:
            self.mediator.play(self.mediator.context.station)

    def pause(self) -> None:
        if self.mediator:
            self.mediator.stop()

    def stop(self) -> None:
        if self.mediator:
            self.mediator.stop()

    def play_pause(self) -> None:
        if self.mediator:
            if self.mediator.context.state.value == "playing":
                self.mediator.stop()
            else:
                self.play()

    def get_volume(self) -> float:
        if self.mediator:
            return self.mediator.context.volume / 100.0
        return 0.5

    def set_volume(self, volume: float) -> None:
        if self.mediator:
            self.mediator.set_volume(int(volume * 100))

    def get_position(self) -> int:
        return 0


if DBUS_AVAILABLE:

    class MprisObject(dbus.service.Object):
        ROOT_INTERFACE = "org.mpris.MediaPlayer2"
        PLAYER_INTERFACE = "org.mpris.MediaPlayer2.Player"

        def __init__(self, bus, path, plugin):
            self._plugin = plugin
            dbus.service.Object.__init__(self, bus, path)

        @dbus.service.method(ROOT_INTERFACE)
        def Raise(self) -> None:
            pass

        @dbus.service.method(ROOT_INTERFACE)
        def Quit(self) -> None:
            pass

        @dbus.service.property(ROOT_INTERFACE, signature="s")
        def Identity(self) -> str:
            return APP_NAME

        @dbus.service.property(ROOT_INTERFACE, signature="b")
        def CanQuit(self) -> bool:
            return True

        @dbus.service.property(ROOT_INTERFACE, signature="b")
        def CanSetFullscreen(self) -> bool:
            return False

        @dbus.service.property(ROOT_INTERFACE, signature="b")
        def CanRaise(self) -> bool:
            return True

        @dbus.service.property(ROOT_INTERFACE, signature="as")
        def SupportedUriSchemes(self) -> list:
            return ["http", "https"]

        @dbus.service.property(ROOT_INTERFACE, signature="as")
        def SupportedMimeTypes(self) -> list:
            return ["audio/mpeg", "audio/x-mpegurl", "audio/x-scpls"]

        @dbus.service.property(PLAYER_INTERFACE, signature="s")
        def PlaybackStatus(self) -> str:
            return getattr(self._plugin, "_playback_status", "Stopped")

        @dbus.service.property(PLAYER_INTERFACE, signature="s")
        def LoopStatus(self) -> str:
            return "None"

        @dbus.service.property(PLAYER_INTERFACE, signature="d")
        def Rate(self) -> float:
            return 1.0

        @dbus.service.property(PLAYER_INTERFACE, signature="b")
        def Shuffle(self) -> bool:
            return False

        @dbus.service.property(PLAYER_INTERFACE, signature="d")
        def Volume(self) -> float:
            return self._plugin.get_volume()

        @Volume.setter
        def Volume(self, value: float) -> None:
            self._plugin.set_volume(value)

        @dbus.service.property(PLAYER_INTERFACE, signature="n")
        def Position(self) -> int:
            return 0

        @dbus.service.property(PLAYER_INTERFACE, signature="d")
        def MinimumRate(self) -> float:
            return 1.0

        @dbus.service.property(PLAYER_INTERFACE, signature="d")
        def MaximumRate(self) -> float:
            return 1.0

        @dbus.service.property(PLAYER_INTERFACE, signature="b")
        def CanGoNext(self) -> bool:
            return True

        @dbus.service.property(PLAYER_INTERFACE, signature="b")
        def CanGoPrevious(self) -> bool:
            return True

        @dbus.service.property(PLAYER_INTERFACE, signature="b")
        def CanSeek(self) -> bool:
            return False

        @dbus.service.property(PLAYER_INTERFACE, signature="b")
        def CanControl(self) -> bool:
            return True

        @dbus.service.method(PLAYER_INTERFACE)
        def Next(self) -> None:
            pass

        @dbus.service.method(PLAYER_INTERFACE)
        def Previous(self) -> None:
            pass

        @dbus.service.method(PLAYER_INTERFACE)
        def Pause(self) -> None:
            self._plugin.pause()

        @dbus.service.method(PLAYER_INTERFACE)
        def PlayPause(self) -> None:
            self._plugin.play_pause()

        @dbus.service.method(PLAYER_INTERFACE)
        def Stop(self) -> None:
            self._plugin.stop()

        @dbus.service.method(PLAYER_INTERFACE)
        def Play(self) -> None:
            self._plugin.play()

        @dbus.service.method(PLAYER_INTERFACE, in_signature="x")
        def SetPosition(self, position: int) -> None:
            pass

        @dbus.service.method(PLAYER_INTERFACE, in_signature="s")
        def Seek(self, offset: int) -> None:
            pass

        @dbus.service.method(PLAYER_INTERFACE, in_signature="o")
        def OpenUri(self, uri: str) -> None:
            pass

        def update_status(self, status: str, station: str) -> None:
            pass

        def update_metadata(self, station: str, artist: str, title: str) -> None:
            pass

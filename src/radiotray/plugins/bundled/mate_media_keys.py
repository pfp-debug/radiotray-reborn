import logging
from typing import TYPE_CHECKING

from radiotray.plugins.base import Plugin

if TYPE_CHECKING:
    from radiotray.config.bookmarks import BookmarkManager
    from radiotray.config.settings import SettingsManager
    from radiotray.core.mediator import StateMediator


class MateMediaKeysPlugin(Plugin):
    name = "MATE Media Keys"
    description = "Multimedia key support for MATE desktop"
    author = "RadioTray Contributors"
    version = "1.0"

    MEDIA_KEYS_SERVICE = "org.mate.SettingsDaemon.MediaKeys"
    MEDIA_KEYS_PATH = "/org/mate/SettingsDaemon/MediaKeys"

    def __init__(self) -> None:
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._bus = None

    def activate(self) -> None:
        self._active = True
        self._connect_to_mate_keys()
        self.logger.info("MATE Media Keys plugin activated")

    def deactivate(self) -> None:
        self._active = False
        self._disconnect_from_mate_keys()
        self.logger.info("MATE Media Keys plugin deactivated")

    def _connect_to_mate_keys(self) -> None:
        try:
            import dbus
            from dbus.mainloop.glib import DBusGMainLoop

            DBusGMainLoop(set_as_default=True)
            self._bus = dbus.SessionBus()

            self._bus.request_name(
                "org.mate.SettingsDaemon.MediaKeys", dbus.bus.NAME_FLAG_DO_NOT_QUEUE
            )

            self._media_keys = self._bus.get_object(self.MEDIA_KEYS_SERVICE, self.MEDIA_KEYS_PATH)

            self._media_keys.connect_to_signal(
                "MediaPlayerKeyPressed",
                self._on_media_key_pressed,
                dbus_interface=self.MEDIA_KEYS_SERVICE,
            )

            self._media_keys.GrabMediaPlayerKeys(
                "radiotray", 0, dbus_interface=self.MEDIA_KEYS_SERVICE
            )

            self.logger.info("Connected to MATE Media Keys")
        except Exception as e:
            self.logger.debug(f"MATE Media Keys not available: {e}")

    def _disconnect_from_mate_keys(self) -> None:
        try:
            if hasattr(self, "_media_keys") and self._media_keys:
                self._media_keys.ReleaseMediaPlayerKeys(
                    "radiotray", dbus_interface=self.MEDIA_KEYS_SERVICE
                )
        except Exception as e:
            self.logger.debug(f"Error releasing MATE keys: {e}")

        if self._bus:
            try:
                self._bus.release_name("org.mate.SettingsDaemon.MediaKeys")
            except Exception:
                pass
            self._bus = None

    def _on_media_key_pressed(self, application: str, key: str) -> None:
        if application != "radiotray":
            return

        self.logger.debug(f"Media key pressed: {key}")

        if key == "Play" or key == "Pause" or key == "PlayPause":
            self._toggle_playback()
        elif key == "Stop":
            self._stop()
        elif key == "Next":
            self._next()
        elif key == "Previous":
            self._previous()

    def _toggle_playback(self) -> None:
        if self.mediator:
            if self.mediator.context.state.value == "playing":
                self.mediator.stop()
            elif self.mediator.context.station:
                self.mediator.play(self.mediator.context.station)

    def _stop(self) -> None:
        if self.mediator:
            self.mediator.stop()

    def _next(self) -> None:
        self.logger.debug("MATE: Next key (not implemented)")

    def _previous(self) -> None:
        self.logger.debug("MATE: Previous key (not implemented)")

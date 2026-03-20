from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from radiotray.config.bookmarks import BookmarkManager
    from radiotray.config.settings import SettingsManager
    from radiotray.core.mediator import StateMediator
    from radiotray.events.manager import EventManager

import logging

DBUS_NAME = "io.github.radiotray"
DBUS_PATH = "/io/github/radiotray"
DBUS_INTERFACE = "io.github.radiotray"


class DBusService:
    def __init__(self, bookmarks: "BookmarkManager", mediator: "StateMediator"):
        self.bookmarks = bookmarks
        self.mediator = mediator
        self.logger = logging.getLogger(__name__)
        self._bus = None
        self._interface = None

    def start(self) -> None:
        try:
            import dbus
            import dbus.service
            import dbus.mainloop.glib
            from gi.repository import GLib

            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            bus = dbus.SessionBus()

            class RadioTrayObject(dbus.service.Object):
                def __init__(self, bookmarks, mediator, path):
                    super().__init__(path)
                    self.bookmarks = bookmarks
                    self.mediator = mediator

                @dbus.service.method(DBUS_INTERFACE, in_signature="", out_signature="as")
                def ListRadios(self):
                    return self.bookmarks.list_radio_names()

                @dbus.service.method(DBUS_INTERFACE, in_signature="", out_signature="s")
                def GetCurrentRadio(self):
                    station = self.mediator.context.station
                    if self.mediator.is_playing():
                        return station
                    return f"{station} (not playing)"

                @dbus.service.method(DBUS_INTERFACE, in_signature="s", out_signature="")
                def PlayRadio(self, name):
                    self.mediator.play(name)

                @dbus.service.method(DBUS_INTERFACE, in_signature="s", out_signature="")
                def PlayUrl(self, url):
                    self.mediator.play_url(url)

                @dbus.service.method(DBUS_INTERFACE, in_signature="", out_signature="")
                def Stop(self):
                    self.mediator.stop()

                @dbus.service.method(DBUS_INTERFACE, in_signature="", out_signature="")
                def Toggle(self):
                    if self.mediator.is_playing():
                        self.mediator.stop()
                    else:
                        self.mediator.play_last()

                @dbus.service.method(DBUS_INTERFACE, in_signature="", out_signature="")
                def VolumeUp(self):
                    self.mediator.volume_up()

                @dbus.service.method(DBUS_INTERFACE, in_signature="", out_signature="")
                def VolumeDown(self):
                    self.mediator.volume_down()

                @dbus.service.method(DBUS_INTERFACE, in_signature="", out_signature="a{ss}")
                def GetMetadata(self):
                    ctx = self.mediator.context
                    return {
                        "station": ctx.station,
                        "title": ctx.title,
                        "artist": ctx.artist or "",
                        "state": ctx.state.value,
                    }

            self._bus = bus
            self._interface = RadioTrayObject(self.bookmarks, self.mediator, DBUS_PATH)
            bus.request_name(DBUS_NAME, dbus.name_flag.IDLE)

            self.logger.info(f"DBus service registered as {DBUS_NAME}")
        except Exception as e:
            self.logger.warning(f"Failed to initialize DBus: {e}")

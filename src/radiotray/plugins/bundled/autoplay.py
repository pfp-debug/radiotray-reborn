from typing import TYPE_CHECKING

from radiotray.plugins.base import Plugin

if TYPE_CHECKING:
    from radiotray.config.bookmarks import BookmarkManager
    from radiotray.config.settings import SettingsManager
    from radiotray.core.mediator import StateMediator


class AutoPlayPlugin(Plugin):
    name = "AutoPlay"
    description = "Resume playback on startup"
    author = "RadioTray Contributors"
    version = "1.0"

    def activate(self) -> None:
        if self.mediator and self.settings:
            last_station = self.settings.get_last_station()
            if last_station:
                self.mediator.play(last_station)
        self._active = True

    def deactivate(self) -> None:
        self._active = False

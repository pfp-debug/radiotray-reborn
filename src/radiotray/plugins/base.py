from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from radiotray.events.manager import EventManager
    from radiotray.config.bookmarks import BookmarkManager
    from radiotray.config.settings import SettingsManager
    from radiotray.core.mediator import StateMediator


class Plugin(ABC):
    """Base class for all plugins."""

    name: str = ""
    description: str = ""
    author: str = ""
    version: str = "1.0"

    def __init__(self) -> None:
        self.event_manager: "EventManager | None" = None
        self.bookmarks: "BookmarkManager | None" = None
        self.settings: "SettingsManager | None" = None
        self.mediator: "StateMediator | None" = None
        self._active = False

    def initialize(
        self,
        event_manager: "EventManager",
        bookmarks: "BookmarkManager",
        settings: "SettingsManager",
        mediator: "StateMediator",
    ) -> None:
        """Initialize the plugin with required dependencies."""
        self.event_manager = event_manager
        self.bookmarks = bookmarks
        self.settings = settings
        self.mediator = mediator

    @abstractmethod
    def activate(self) -> None:
        """Called when the plugin is activated."""
        ...

    def deactivate(self) -> None:
        """Called when the plugin is deactivated."""
        self._active = False

    def on_event(self, event: str, data: dict) -> None:
        """Handle events from the event manager."""
        pass

    def is_active(self) -> bool:
        """Check if the plugin is active."""
        return self._active

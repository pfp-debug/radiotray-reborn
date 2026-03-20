from typing import Callable
from dataclasses import dataclass, field


@dataclass
class Event:
    name: str
    data: dict = field(default_factory=dict)


class EventManager:
    STATE_CHANGED = "state_changed"
    SONG_CHANGED = "song_changed"
    STATION_ERROR = "station_error"
    VOLUME_CHANGED = "volume_changed"
    BOOKMARKS_RELOADED = "bookmarks_reloaded"
    NOTIFICATION = "notification"

    def __init__(self) -> None:
        self._observers: dict[str, list[Callable]] = {
            self.STATE_CHANGED: [],
            self.SONG_CHANGED: [],
            self.STATION_ERROR: [],
            self.VOLUME_CHANGED: [],
            self.BOOKMARKS_RELOADED: [],
            self.NOTIFICATION: [],
        }

    def subscribe(self, event: str, callback: Callable[[dict], None]) -> None:
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"EventManager: Subscribing {callback.__name__} to {event}")
        if event in self._observers:
            self._observers[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable[[dict], None]) -> None:
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"EventManager: Unsubscribing {callback.__name__} from {event}")
        if event in self._observers and callback in self._observers[event]:
            self._observers[event].remove(callback)

    def notify(self, event: str, data: dict | None = None) -> None:
        import logging
        import traceback

        logger = logging.getLogger(__name__)
        if event not in self._observers:
            return
        event_data = data or {}
        logger.info(f"EventManager: Notifying {len(self._observers[event])} observers for {event}")
        for callback in self._observers[event]:
            try:
                logger.info(f"EventManager: Calling {callback}")
                callback(event_data)
                logger.info(f"EventManager: {callback} completed")
            except Exception as e:
                logger.error(f"EventManager: Callback error: {e}")
                logger.error(traceback.format_exc())

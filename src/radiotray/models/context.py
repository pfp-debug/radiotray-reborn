from dataclasses import dataclass, field
from enum import Enum


class PlaybackState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    CONNECTING = "connecting"
    PAUSED = "paused"


@dataclass
class Context:
    state: PlaybackState = PlaybackState.STOPPED
    station: str = ""
    url: str = ""
    title: str = ""
    artist: str = ""
    album: str = ""
    volume: float = 1.0

    def reset_song_info(self) -> None:
        self.title = ""
        self.artist = ""
        self.album = ""

    def get_song_info(self) -> str:
        if self.title and self.artist:
            return f"{self.artist} - {self.title}"
        elif self.title:
            return self.title
        elif self.artist:
            return self.artist
        return "Playing"

    def get_volume_percent(self) -> int:
        return int(round(self.volume * 100))

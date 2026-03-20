from abc import ABC, abstractmethod
from typing import ClassVar


class PlaylistDecoder(ABC):
    content_types: ClassVar[list[str]] = []
    name: ClassVar[str] = "base"

    @abstractmethod
    def is_stream_valid(self, content_type: str, first_bytes: bytes) -> bool: ...

    @abstractmethod
    def extract_playlist(self, url: str) -> list[str]: ...

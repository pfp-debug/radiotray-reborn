from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from radiotray.decoders.base import PlaylistDecoder


@dataclass
class UrlInfo:
    url: str
    is_playlist: bool
    content_type: str | None
    decoder: "PlaylistDecoder | None" = None

    def get_url(self) -> str:
        return self.url

    def get_decoder(self) -> "PlaylistDecoder | None":
        return self.decoder

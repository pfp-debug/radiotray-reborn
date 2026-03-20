import logging

from radiotray.decoders.base import PlaylistDecoder
from radiotray.constants import get_default_http_headers


class PlsDecoder(PlaylistDecoder):
    content_types = ["audio/x-scpls", "application/pls+xml"]
    name = "pls"

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def is_stream_valid(self, content_type: str, first_bytes: bytes) -> bool:
        if any(ct in content_type for ct in self.content_types):
            return True
        return first_bytes.strip().lower().startswith(b"[playlist]")

    def extract_playlist(self, url: str) -> list[str]:
        import requests

        self.logger.info(f"Downloading PLS playlist: {url}")
        resp = requests.get(url, headers=get_default_http_headers(), timeout=30)
        resp.raise_for_status()

        playlist: list[str] = []
        for line in resp.text.splitlines():
            if line.lower().startswith("file"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    playlist.append(parts[1].strip())

        self.logger.debug(f"Extracted {len(playlist)} streams from PLS")
        return playlist

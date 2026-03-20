import logging

from radiotray.decoders.base import PlaylistDecoder
from radiotray.constants import get_default_http_headers


class RamDecoder(PlaylistDecoder):
    content_types = ["audio/x-pn-realaudio", "audio/x-pn-realaudio-plugin"]
    name = "ram"

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def is_stream_valid(self, content_type: str, first_bytes: bytes) -> bool:
        if any(ct in content_type for ct in self.content_types):
            return True
        return b"rtsp://" in first_bytes.lower() or b"pnm://" in first_bytes.lower()

    def extract_playlist(self, url: str) -> list[str]:
        import requests

        self.logger.info(f"Downloading RAM playlist: {url}")
        resp = requests.get(url, headers=get_default_http_headers(), timeout=30)
        resp.raise_for_status()

        playlist: list[str] = []
        for line in resp.text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                if line.startswith("rtsp"):
                    line = line.replace("rtsp://", "http://")
                elif line.startswith("pnm"):
                    line = line.replace("pnm://", "http://")
                playlist.append(line)

        self.logger.debug(f"Extracted {len(playlist)} streams from RAM")
        return playlist

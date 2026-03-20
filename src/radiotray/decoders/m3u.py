import logging

from radiotray.decoders.base import PlaylistDecoder
from radiotray.constants import get_default_http_headers


class M3uDecoder(PlaylistDecoder):
    content_types = ["audio/x-mpegurl", "application/x-mpegurl", "application/m3u"]
    name = "m3u"

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def is_stream_valid(self, content_type: str, first_bytes: bytes) -> bool:
        if any(ct in content_type for ct in self.content_types):
            return True
        return (
            b"#EXTM3U" in first_bytes
            or first_bytes.strip().endswith(b".mp3")
            or b".mp3" in first_bytes
        )

    def extract_playlist(self, url: str) -> list[str]:
        import requests

        self.logger.info(f"Downloading M3U playlist: {url}")
        resp = requests.get(url, headers=get_default_http_headers(), timeout=30)
        resp.raise_for_status()

        playlist: list[str] = []
        for line in resp.text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                if line.startswith("http"):
                    playlist.append(line)
                elif not line.startswith("/"):
                    from urllib.parse import urljoin

                    playlist.append(urljoin(url, line))

        self.logger.debug(f"Extracted {len(playlist)} streams from M3U")
        return playlist

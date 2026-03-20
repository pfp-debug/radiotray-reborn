import logging
import re

from radiotray.decoders.base import PlaylistDecoder
from radiotray.constants import get_default_http_headers


class AsfDecoder(PlaylistDecoder):
    content_types = ["audio/x-ms-wax", "video/x-ms-wvx", "video/x-ms-wmx"]
    name = "asf"

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def is_stream_valid(self, content_type: str, first_bytes: bytes) -> bool:
        if any(ct in content_type for ct in self.content_types):
            return True
        lower = first_bytes.lower()
        return b"[reference]" in lower

    def extract_playlist(self, url: str) -> list[str]:
        import requests

        self.logger.info(f"Downloading ASF playlist: {url}")
        resp = requests.get(url, headers=get_default_http_headers(), timeout=30)
        resp.raise_for_status()

        playlist: list[str] = []
        ref_pattern = re.compile(r"ref\d+\s*=\s*(.+)", re.IGNORECASE)
        for match in ref_pattern.finditer(resp.text):
            stream_url = match.group(1).strip()
            if stream_url.startswith("mms"):
                stream_url = stream_url.replace("mms://", "http://")
            playlist.append(stream_url)

        self.logger.debug(f"Extracted {len(playlist)} streams from ASF")
        return playlist

import logging
import re

from radiotray.decoders.base import PlaylistDecoder
from radiotray.constants import get_default_http_headers


class AsxDecoder(PlaylistDecoder):
    content_types = ["video/x-ms-asf", "application/vnd.ms-asf", "audio/x-ms-wax"]
    name = "asx"

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def is_stream_valid(self, content_type: str, first_bytes: bytes) -> bool:
        if any(ct in content_type for ct in self.content_types):
            return True
        lower = first_bytes.lower()
        return b"<asx" in lower or b"[reference]" in lower

    def extract_playlist(self, url: str) -> list[str]:
        import requests

        self.logger.info(f"Downloading ASX playlist: {url}")
        resp = requests.get(url, headers=get_default_http_headers(), timeout=30)
        resp.raise_for_status()

        content = resp.text.lower()
        playlist: list[str] = []

        href_pattern = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
        for match in href_pattern.finditer(content):
            stream_url = match.group(1)
            if stream_url.startswith("mms"):
                stream_url = stream_url.replace("mms://", "http://")
            playlist.append(stream_url)

        ref_pattern = re.compile(r'ref\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
        for match in ref_pattern.finditer(content):
            stream_url = match.group(1)
            if stream_url.startswith("mms"):
                stream_url = stream_url.replace("mms://", "http://")
            playlist.append(stream_url)

        self.logger.debug(f"Extracted {len(playlist)} streams from ASX")
        return playlist

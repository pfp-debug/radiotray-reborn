import logging
import xml.etree.ElementTree as ET

from radiotray.decoders.base import PlaylistDecoder
from radiotray.constants import get_default_http_headers


class XspfDecoder(PlaylistDecoder):
    content_types = ["application/xspf+xml", "application/x-xspf"]
    name = "xspf"

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def is_stream_valid(self, content_type: str, first_bytes: bytes) -> bool:
        if any(ct in content_type for ct in self.content_types):
            return True
        return b"<playlist" in first_bytes.lower() and b"xmlns=" in first_bytes.lower()

    def extract_playlist(self, url: str) -> list[str]:
        import requests

        self.logger.info(f"Downloading XSPF playlist: {url}")
        resp = requests.get(url, headers=get_default_http_headers(), timeout=30)
        resp.raise_for_status()

        playlist: list[str] = []
        try:
            root = ET.fromstring(resp.text)
            ns = {"xspf": "http://xspf.org/ns/0/"}
            for track in root.findall(".//xspf:track", ns):
                location = track.find("xspf:location", ns)
                if location is not None and location.text:
                    playlist.append(location.text.strip())
        except ET.ParseError as e:
            self.logger.warning(f"Failed to parse XSPF: {e}")

        self.logger.debug(f"Extracted {len(playlist)} streams from XSPF")
        return playlist

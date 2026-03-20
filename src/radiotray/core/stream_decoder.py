import logging
from typing import TYPE_CHECKING

from radiotray.models.url_info import UrlInfo
from radiotray.constants import get_default_http_headers
from radiotray.decoders import (
    PlsDecoder,
    M3uDecoder,
    AsxDecoder,
    XspfDecoder,
    AsfDecoder,
    RamDecoder,
)
import requests

if TYPE_CHECKING:
    from radiotray.config.settings import SettingsManager


class StreamDecoder:
    def __init__(self, settings: "SettingsManager") -> None:
        self.decoders = [
            PlsDecoder(),
            M3uDecoder(),
            AsxDecoder(),
            XspfDecoder(),
            AsfDecoder(),
            RamDecoder(),
        ]
        self.timeout = settings.get_url_timeout()
        self.logger = logging.getLogger(__name__)

    def get_media_info(self, url: str) -> UrlInfo | None:
        if not url.startswith("http"):
            self.logger.info(f"Not HTTP URL, treating as direct stream: {url}")
            return UrlInfo(url=url, is_playlist=False, content_type=None)

        self.logger.info(f"Requesting stream info: {url}")
        try:
            resp = requests.get(
                url,
                stream=True,
                timeout=float(self.timeout) / 1000,
                headers=get_default_http_headers(),
            )
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "")
            first_bytes = next(resp.iter_content(500), b"")
            resp.close()
        except requests.RequestException as e:
            self.logger.warning(f"Failed to get stream info: {e}")
            return None

        self.logger.debug(f"Content-Type: {content_type}")
        for decoder in self.decoders:
            if decoder.is_stream_valid(content_type, first_bytes):
                self.logger.info(f"Matched decoder: {decoder.name}")
                return UrlInfo(
                    url=url, is_playlist=True, content_type=content_type, decoder=decoder
                )

        self.logger.info("No playlist decoder matched, treating as direct stream")
        return UrlInfo(url=url, is_playlist=False, content_type=content_type)

    def get_playlist(self, url_info: UrlInfo) -> list[str]:
        if url_info.decoder:
            return url_info.decoder.extract_playlist(url_info.url)
        return []

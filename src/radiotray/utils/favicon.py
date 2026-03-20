import logging
from pathlib import Path
from urllib.parse import urlparse
import requests

from radiotray.constants import USER_DATA_PATH

ICON_CACHE_DIR = USER_DATA_PATH / "icons"


class FaviconGrabber:
    DEFAULT_ICON = USER_DATA_PATH / "radio.png"
    GOOGLE_FAVICON_API = "https://www.google.com/s2/favicons?domain={domain}&sz=32"

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.timeout = 3
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        )
        ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def get_favicon_for_url(self, stream_url: str) -> Path:
        if not stream_url:
            return self.DEFAULT_ICON

        parsed = urlparse(stream_url)
        domain = parsed.netloc

        cached = self._get_favicon_from_cache(domain)
        if cached and cached.exists():
            return cached

        icon = self._download_google_favicon(domain)
        if icon and icon.exists():
            return icon

        return self.DEFAULT_ICON

    def _download_google_favicon(self, domain: str) -> Path | None:
        try:
            favicon_url = self.GOOGLE_FAVICON_API.format(domain=domain)
            resp = self.session.get(favicon_url, timeout=self.timeout)
            if resp.status_code != 200:
                return None

            content_type = resp.headers.get("content-type", "")
            if "image" not in content_type:
                return None

            ext = ".png" if "png" in content_type else ".ico"
            icon_path = self._get_cache_path(domain, ext)

            with open(icon_path, "wb") as f:
                f.write(resp.content)

            self.logger.info(f"Downloaded favicon for {domain}")
            return icon_path
        except Exception as e:
            self.logger.debug(f"Failed to download favicon for {domain}: {e}")
            return None

    def _get_cache_path(self, domain: str, ext: str = ".ico") -> Path:
        safe_domain = domain.replace(":", "_").replace(".", "_")
        return ICON_CACHE_DIR / f"{safe_domain}{ext}"

    def _get_favicon_from_cache(self, domain: str) -> Path | None:
        for ext in [".ico", ".png", ".jpg", ".svg", ".webp"]:
            path = ICON_CACHE_DIR / f"{domain.replace(':', '_').replace('.', '_')}{ext}"
            if path.exists():
                return path
        return None

    def grab_favicon_async(self, stream_url: str, callback=None):
        import threading

        def _grab():
            icon_path = self.get_favicon_for_url(stream_url)
            if callback:
                callback(icon_path)

        thread = threading.Thread(target=_grab, daemon=True)
        thread.start()
        return thread

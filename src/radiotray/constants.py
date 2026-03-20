from pathlib import Path

from xdg.BaseDirectory import xdg_data_home

APP_NAME = "RadioTray [reborn]"
APP_ID = "radiotray"
VERSION = "0.7.5"

USER_DATA_PATH = Path(xdg_data_home) / APP_ID
LOG_FILE = USER_DATA_PATH / "radiotray.log"

USER_AGENT = f"RadioTray/{VERSION}"


def _find_data_path() -> Path:
    src_data = Path(__file__).parent.parent.parent.parent / "data"
    if src_data.exists():
        return src_data
    for prefix in (Path("/usr"), Path("/usr/local")):
        candidate = prefix / "share" / APP_ID
        if candidate.exists():
            return candidate
    return Path("/usr") / "share" / APP_ID


def _find_bundled_plugins_path() -> Path:
    src_path = Path(__file__).parent.parent / "plugins" / "bundled"
    if src_path.exists():
        return src_path
    for prefix in (Path("/usr"), Path("/usr/local")):
        candidate = prefix / "lib" / "python3" / "dist-packages" / APP_ID / "plugins" / "bundled"
        if candidate.exists():
            return candidate
    return Path("/usr") / "lib" / "python3" / "dist-packages" / APP_ID / "plugins" / "bundled"


DATA_PATH = _find_data_path()
BUNDLED_PLUGINS_PATH = _find_bundled_plugins_path()


def get_default_http_headers() -> dict[str, str]:
    return {"User-Agent": USER_AGENT}


DEFAULT_BOOKMARKS = DATA_PATH / "bookmarks.xml"
DEFAULT_SETTINGS = DATA_PATH / "config.xml"
IMAGES_PATH = DATA_PATH / "images"
SYSTEM_PLUGINS_PATH = DATA_PATH / "plugins"

USER_BOOKMARKS = USER_DATA_PATH / "bookmarks.xml"
USER_SETTINGS = USER_DATA_PATH / "config.xml"
USER_PLUGINS = USER_DATA_PATH / "plugins"

ICON_ON = IMAGES_PATH / "radiotray_on.png"
ICON_OFF = IMAGES_PATH / "radiotray_off.png"
ICON_CONNECTING = IMAGES_PATH / "radiotray_connecting.gif"
APP_ICON = IMAGES_PATH / "radiotray.png"

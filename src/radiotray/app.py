import ctypes
import fcntl
import logging
import logging.handlers
import os
import signal
import sys
from pathlib import Path
from shutil import copy2

libc = ctypes.CDLL("libc.so.6", use_errno=True)


def set_process_name(name: str) -> None:
    try:
        libc.prctl(15, name.encode(), 0, 0, 0)
    except Exception:
        pass


from gi.repository import Gst, GLib, Gtk

from radiotray.constants import APP_NAME, USER_DATA_PATH, LOG_FILE
from radiotray.constants import (
    DEFAULT_BOOKMARKS,
    DEFAULT_SETTINGS,
    USER_BOOKMARKS,
    USER_SETTINGS,
)
from radiotray.config.bookmarks import BookmarkManager
from radiotray.config.settings import SettingsManager
from radiotray.core.mediator import StateMediator
from radiotray.core.player import GStreamerPlayer
from radiotray.dbus.facade import DBusService
from radiotray.events.manager import EventManager
from radiotray.gui.tray import TrayIcon
from radiotray.plugins.manager import PluginManager


PID_FILE = USER_DATA_PATH / "radiotray.pid"
LOCK_FILE = USER_DATA_PATH / "radiotray.lock"
_lock_fd = None


def check_single_instance() -> bool:
    USER_DATA_PATH.mkdir(parents=True, exist_ok=True)

    if PID_FILE.exists():
        try:
            with open(PID_FILE, "r") as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, signal.SIGTERM)
            print(f"Killed existing RadioTray instance (PID: {old_pid})", file=sys.stderr)
            import time

            time.sleep(0.5)
        except (ProcessLookupError, ValueError, OSError):
            pass

    global _lock_fd
    try:
        _lock_fd = os.open(str(LOCK_FILE), os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, IOError) as e:
        if _lock_fd is not None:
            os.close(_lock_fd)
            _lock_fd = None
        return False

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    def cleanup(signum, frame):
        if PID_FILE.exists():
            PID_FILE.unlink()
        if _lock_fd is not None:
            try:
                fcntl.flock(_lock_fd, fcntl.LOCK_UN)
                os.close(_lock_fd)
            except (OSError, IOError):
                pass
        os._exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGHUP, cleanup)

    return True


class RadioTrayApp:
    def __init__(self, url: str | None = None, resume: bool = False):
        set_process_name("radiotray")
        self.url = url
        self.resume = resume
        self._setup_logging()
        self._setup_paths()
        self.logger = logging.getLogger(__name__)
        self.event_manager = EventManager()
        self._init_components()

    def _setup_logging(self) -> None:
        self.logger = logging.getLogger("radiotray")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = True
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=1)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def _setup_paths(self) -> None:
        USER_DATA_PATH.mkdir(parents=True, exist_ok=True)
        (USER_DATA_PATH / "plugins").mkdir(exist_ok=True)

        if not USER_BOOKMARKS.exists():
            self.logger.info("Copying default bookmarks")
            copy2(DEFAULT_BOOKMARKS, USER_BOOKMARKS)

        if not USER_SETTINGS.exists():
            self.logger.info("Copying default settings")
            copy2(DEFAULT_SETTINGS, USER_SETTINGS)

    def _init_components(self) -> None:
        self.bookmarks = BookmarkManager(USER_BOOKMARKS)
        self.bookmarks.load()

        self.settings = SettingsManager(USER_SETTINGS)
        self.settings.load()

        self.mediator = StateMediator(self.bookmarks, self.settings, self.event_manager)

        Gst.init(None)
        self.player = GStreamerPlayer(self.mediator, self.settings, self.event_manager)

        self.mediator.set_player(self.player)

        self.plugin_manager = PluginManager(
            self.event_manager,
            self.bookmarks,
            self.settings,
            self.mediator,
            Gtk.Menu(),
        )
        self.plugin_manager.discover_plugins()

        self.tray = TrayIcon(
            self.mediator,
            self.bookmarks,
            self.settings,
            self.event_manager,
            self.plugin_manager,
        )

        GLib.timeout_add(100, self._delayed_start)

    def _delayed_start(self) -> bool:
        if self.url:
            self.mediator.play_url(self.url)
        elif self.resume:
            self.mediator.play_last()
        return False

    def _setup_dbus(self) -> None:
        try:
            self.dbus_service = DBusService(self.bookmarks, self.mediator)
        except Exception as e:
            self.logger.warning(f"Failed to initialize DBus: {e}")
            self.dbus_service = None

    def run(self) -> int:
        self.logger.info(f"Starting {APP_NAME}")
        self.tray.run()
        return 0

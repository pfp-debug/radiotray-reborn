from dataclasses import dataclass
from pathlib import Path
import configparser
import logging
import importlib
import sys
from typing import TYPE_CHECKING

from radiotray.constants import USER_PLUGINS, DATA_PATH, BUNDLED_PLUGINS_PATH
from radiotray.plugins.base import Plugin

if TYPE_CHECKING:
    from radiotray.events.manager import EventManager
    from radiotray.config.bookmarks import BookmarkManager
    from radiotray.config.settings import SettingsManager
    from radiotray.core.mediator import StateMediator
    from gi.repository import Gtk


@dataclass
class PluginInfo:
    name: str
    description: str
    author: str
    version: str
    module: str
    cls_name: str
    path: Path
    instance: Plugin | None = None


class PluginManager:
    def __init__(
        self,
        event_manager: "EventManager",
        bookmarks: "BookmarkManager",
        settings: "SettingsManager",
        mediator: "StateMediator",
        plugin_menu: "Gtk.Menu",
    ) -> None:
        self.event_manager = event_manager
        self.bookmarks = bookmarks
        self.settings = settings
        self.mediator = mediator
        self.plugin_menu = plugin_menu
        self.logger = logging.getLogger(__name__)
        self.plugin_infos: dict[str, PluginInfo] = {}

    def discover_plugins(self) -> None:
        """Discover plugins from system and user directories."""
        plugin_paths = []

        system_plugins = DATA_PATH / "plugins"
        if system_plugins.exists():
            plugin_paths.extend(system_plugins.glob("*.plugin"))

        if USER_PLUGINS.exists():
            plugin_paths.extend(USER_PLUGINS.glob("*.plugin"))

        for plugin_file in plugin_paths:
            info = self._parse_plugin_file(plugin_file)
            if info:
                self.plugin_infos[info.name] = info
                self._load_plugin(info)

    def _parse_plugin_file(self, path: Path) -> PluginInfo | None:
        """Parse a .plugin manifest file."""
        try:
            config = configparser.ConfigParser()
            config.read(path)

            if "Plugin" not in config:
                self.logger.warning(f"Invalid plugin file: {path}")
                return None

            section = config["Plugin"]
            return PluginInfo(
                name=section.get("name", ""),
                description=section.get("description", ""),
                author=section.get("author", ""),
                version=section.get("version", "1.0"),
                module=section.get("module", ""),
                cls_name=section.get("class", ""),
                path=path,
            )
        except Exception as e:
            self.logger.error(f"Failed to parse plugin file {path}: {e}")
            return None

    def _load_plugin(self, info: PluginInfo) -> None:
        """Load and instantiate a plugin."""
        if not info.module:
            return

        try:
            bundled_path = str(BUNDLED_PLUGINS_PATH)
            if bundled_path not in sys.path:
                sys.path.insert(0, bundled_path)

            module = importlib.import_module(info.module)
            cls = getattr(module, info.cls_name)
            info.instance = cls()
            self.logger.info(f"Loaded plugin: {info.name}")
        except Exception as e:
            self.logger.error(f"Failed to load plugin {info.name}: {e}")

    def activate_all(self) -> None:
        """Activate all configured plugins."""
        active_plugins = self.settings.get_list("active_plugins")

        for name, info in self.plugin_infos.items():
            if name in active_plugins and info.instance:
                try:
                    info.instance.initialize(
                        self.event_manager,
                        self.bookmarks,
                        self.settings,
                        self.mediator,
                    )
                    info.instance.activate()
                    info.instance._active = True
                    self.logger.info(f"Activated plugin: {name}")
                except Exception as e:
                    self.logger.error(f"Failed to activate plugin {name}: {e}")

    def activate_plugin(self, name: str) -> bool:
        """Activate a specific plugin."""
        if name in self.plugin_infos:
            info = self.plugin_infos[name]
            if info.instance:
                info.instance.initialize(
                    self.event_manager, self.bookmarks, self.settings, self.mediator
                )
                info.instance.activate()
                info.instance._active = True
                return True
        return False

    def deactivate_plugin(self, name: str) -> bool:
        """Deactivate a specific plugin."""
        if name in self.plugin_infos:
            info = self.plugin_infos[name]
            if info.instance:
                info.instance.deactivate()
                return True
        return False

    def get_plugins(self) -> list[PluginInfo]:
        """Get all discovered plugins."""
        return list(self.plugin_infos.values())

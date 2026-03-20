import html
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from gi.repository import Gtk, Gdk, GdkPixbuf

from radiotray.constants import APP_NAME, ICON_ON, ICON_OFF, ICON_CONNECTING
from radiotray.utils.favicon import FaviconGrabber

if TYPE_CHECKING:
    from radiotray.core.mediator import StateMediator
    from radiotray.config.bookmarks import BookmarkManager
    from radiotray.config.settings import SettingsManager
    from radiotray.events.manager import EventManager


class TrayIcon:
    def __init__(
        self,
        mediator: "StateMediator",
        bookmarks: "BookmarkManager",
        settings: "SettingsManager",
        event_manager: "EventManager",
        plugin_manager: "PluginManager | None" = None,
    ) -> None:
        self.mediator = mediator
        self.bookmarks = bookmarks
        self.settings = settings
        self.event_manager = event_manager
        self.plugin_manager = plugin_manager
        self.logger = logging.getLogger(__name__)
        self.favicon_grabber = FaviconGrabber()
        self._icon_cache: dict[str, GdkPixbuf.Pixbuf] = {}

        self.radio_menu: Gtk.Menu | None = None
        self.turn_on_off: Gtk.MenuItem | None = None
        self.turn_on_off2: Gtk.MenuItem | None = None
        self.menu: Gtk.Menu | None = None
        self.plugin_menu: Gtk.Menu | None = None
        self.icon: Gtk.StatusIcon | None = None
        self.editor_plugin = None

    def build_menu(self) -> None:
        self.radio_menu = Gtk.Menu()
        self.menu = Gtk.Menu()

        self._build_radio_menu()
        self._build_config_menu()

        self.icon = Gtk.StatusIcon()
        self.icon.set_from_file(str(ICON_OFF))
        self.icon.set_tooltip_markup(self._get_tooltip_text())
        self.icon.connect("button_press_event", self._on_button_press)
        self.icon.connect("scroll_event", self._on_scroll)
        self.icon.set_visible(True)

        self.event_manager.subscribe(self.event_manager.STATE_CHANGED, self._on_state_changed)
        self.event_manager.subscribe(self.event_manager.SONG_CHANGED, self._on_song_changed)
        self.event_manager.subscribe(self.event_manager.VOLUME_CHANGED, self._on_volume_changed)
        self.event_manager.subscribe(
            self.event_manager.BOOKMARKS_RELOADED, self._on_bookmarks_reloaded
        )

        if self.plugin_manager:
            self.plugin_manager.plugin_menu = self.plugin_menu
            self.plugin_manager.activate_all()
            self._populate_plugin_menu()

    def _build_radio_menu(self) -> None:
        if not self.mediator.context.station:
            self.turn_on_off = Gtk.MenuItem(label="Turned Off")
            self.turn_on_off.set_sensitive(False)
        else:
            self.turn_on_off = Gtk.MenuItem(label=f'Turn On "{self.mediator.context.station}"')
            self.turn_on_off.set_sensitive(True)

        self.turn_on_off.connect("activate", self._on_turn_on_off)

        self._update_radios_menu()
        self.radio_menu.show_all()

    def _update_radios_menu(self) -> None:
        for child in self.radio_menu.get_children():
            self.radio_menu.remove(child)

        self._sync_turn_on_off_label()
        self.radio_menu.append(self.turn_on_off)
        self.turn_on_off.show()

        separator = Gtk.SeparatorMenuItem()
        self.radio_menu.append(separator)
        separator.show()

        self.bookmarks.walk_bookmarks(
            self._group_callback, self._bookmark_callback, self.radio_menu
        )
        self.radio_menu.show_all()

    def _sync_turn_on_off_label(self) -> None:
        if not self.mediator.context.station:
            self.turn_on_off.set_label("Turned Off")
            self.turn_on_off.set_sensitive(False)
        elif self.mediator.context.state.value in ("playing", "connecting"):
            self.turn_on_off.set_label(f'Turn Off "{self.mediator.context.station}"')
            self.turn_on_off.set_sensitive(True)
        else:
            self.turn_on_off.set_label(f'Turn On "{self.mediator.context.station}"')
            self.turn_on_off.set_sensitive(True)

    def _build_config_menu(self) -> None:
        self.turn_on_off2 = Gtk.MenuItem(label="Turned Off")
        self.turn_on_off2.set_sensitive(False)
        self.turn_on_off2.connect("activate", self._on_turn_on_off)

        separator = Gtk.SeparatorMenuItem()

        menu_item3 = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_ABOUT, None)
        menu_item2 = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_QUIT, None)

        self.menu.append(self.turn_on_off2)
        self.menu.append(separator)

        menu_plugins_item = Gtk.MenuItem(label="Plugins")
        self.plugin_menu = Gtk.Menu()
        menu_plugins_item.set_submenu(self.plugin_menu)
        menu_item5 = Gtk.MenuItem(label="Configure Plugins...")
        self.plugin_menu.append(menu_item5)
        self.plugin_menu.append(Gtk.SeparatorMenuItem())
        self.menu.append(menu_plugins_item)

        self.menu.append(Gtk.SeparatorMenuItem())
        self.menu.append(menu_item3)
        self.menu.append(menu_item2)

        menu_item2.show()
        menu_item3.show()
        self.turn_on_off2.show()
        separator.show()

        menu_item2.connect("activate", self._on_quit)
        menu_item3.connect("activate", self._on_about)
        menu_item5.connect("activate", self._on_plugin_preferences)

        self.menu.show_all()

    def _populate_plugin_menu(self) -> None:
        if not self.plugin_manager or not self.plugin_menu:
            self.logger.error("Cannot populate plugin menu: manager or menu is None")
            return

        for child in list(self.plugin_menu.get_children()):
            self.plugin_menu.remove(child)

        menu_item5 = Gtk.MenuItem(label="Configure Plugins...")
        menu_item5.connect("activate", self._on_plugin_preferences)
        self.plugin_menu.append(menu_item5)
        self.plugin_menu.append(Gtk.SeparatorMenuItem())

        active_plugins = self.plugin_manager.settings.get_list("active_plugins")
        self.logger.info(f"Active plugins: {active_plugins}")

        for info in self.plugin_manager.get_plugins():
            if info.name not in active_plugins:
                self.logger.debug(f"Skipping {info.name} - not active")
                continue
            if info.name == "Editor":
                self.editor_plugin = info.instance
                self.logger.info(f"Editor plugin instance: {info.instance}")
            if info.instance and hasattr(info.instance, "get_menu_item"):
                try:
                    menu_item = info.instance.get_menu_item()
                    if menu_item:
                        self.plugin_menu.append(menu_item)
                        self.logger.info(f"Added menu item for {info.name}")
                    else:
                        self.logger.warning(f"get_menu_item returned None for {info.name}")
                except Exception as e:
                    self.logger.warning(f"Failed to add menu item for plugin {info.name}: {e}")
            else:
                self.logger.warning(f"Plugin {info.name} has no get_menu_item method")

        self.plugin_menu.show_all()
        self.logger.info(f"Plugin menu populated with {len(active_plugins)} active plugins")

    def _group_callback(self, group_name: str, user_data: Gtk.Menu) -> Gtk.Menu:
        if group_name == "root":
            return user_data
        group = Gtk.ImageMenuItem(label=group_name)
        icon = self._get_group_icon(group_name)
        if icon:
            group.set_image(Gtk.Image.new_from_pixbuf(icon))
        user_data.append(group)
        submenu = Gtk.Menu()
        group.set_submenu(submenu)
        return submenu

    def _get_group_icon(self, group_name: str) -> GdkPixbuf.Pixbuf | None:
        icon_path = self.bookmarks.get_group_icon(group_name)
        if icon_path and Path(icon_path).exists():
            try:
                return GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, 16, 16)
            except:
                pass
        return self._get_default_folder_icon()

    def _bookmark_callback(self, radio_name: str, user_data: Gtk.Menu) -> None:
        if radio_name.startswith("["):
            return
        radio = Gtk.ImageMenuItem(label=radio_name)
        radio.connect("activate", self._on_start_radio, radio_name)
        icon = self._get_radio_icon(radio_name)
        if icon:
            radio.set_image(Gtk.Image.new_from_pixbuf(icon))
        user_data.append(radio)

    def _on_button_press(self, icon: Gtk.StatusIcon, event: Gdk.EventButton) -> bool:
        if event.button == 1:
            self.radio_menu.popup(
                None, None, Gtk.StatusIcon.position_menu, icon, event.button, event.get_time()
            )
        elif event.button == 2:
            if self.mediator.context.state.value == "playing":
                self.mediator.stop()
            else:
                if self.mediator.context.station:
                    self.mediator.play(self.mediator.context.station)
        else:
            self.menu.popup(
                None, None, Gtk.StatusIcon.position_menu, icon, event.button, event.get_time()
            )
        return True

    def _on_scroll(self, widget: Gtk.Widget, event: Gdk.EventScroll) -> bool:
        if event.direction == Gdk.ScrollDirection.UP:
            self.mediator.volume_up()
        elif event.direction == Gdk.ScrollDirection.DOWN:
            self.mediator.volume_down()
        return True

    def _on_turn_on_off(self, _widget: Gtk.Widget) -> None:
        self.logger.info(f"_on_turn_on_off: current state = {self.mediator.context.state}")
        if self.mediator.context.state.value in ("playing", "connecting"):
            self.logger.info("Stopping playback")
            self.mediator.stop()
        else:
            if self.mediator.context.station:
                self.logger.info(f"Starting playback: {self.mediator.context.station}")
                self.mediator.play(self.mediator.context.station)

    def _on_start_radio(self, _widget: Gtk.Widget, radio_name: str) -> None:
        self.mediator.play(radio_name)

    def _on_preferences(self, _widget: Gtk.Widget) -> None:
        dialog = Gtk.Dialog(title="Configure Radios", transient_for=None, flags=0)
        dialog.add_button("Save", Gtk.ResponseType.OK)
        dialog.set_default_size(500, 400)

        notebook = Gtk.Notebook()
        dialog.vbox.pack_start(notebook, True, True, 0)

        bookmarks_page = self._create_bookmarks_page()
        notebook.append_page(bookmarks_page, Gtk.Label(label="Bookmarks"))

        dialog.show_all()
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self._on_save_bookmarks()
        dialog.destroy()

    def _create_bookmarks_page(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        box.set_border_width(10)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)

        self._bookmarks_store = Gtk.TreeStore(GdkPixbuf.Pixbuf, str, str)
        self._tree_view = Gtk.TreeView(model=self._bookmarks_store)
        self._tree_view.connect("row-activated", self._on_row_activated)

        renderer_pixbuf = Gtk.CellRendererPixbuf()
        col = Gtk.TreeViewColumn()
        col.pack_start(renderer_pixbuf, False)
        col.add_attribute(renderer_pixbuf, "pixbuf", 0)

        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, "text", 1)
        self._tree_view.append_column(col)

        scrolled.add(self._tree_view)
        box.pack_start(scrolled, True, True, 0)

        button_box = Gtk.ButtonBox(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_layout(Gtk.ButtonBoxStyle.END)

        add_group_btn = Gtk.Button(label="Add Group")
        add_group_btn.connect("clicked", lambda _: self._add_group())
        add_btn = Gtk.Button(label="Add Station")
        add_btn.connect("clicked", lambda _: self._add_station())
        remove_btn = Gtk.Button(label="Remove")
        remove_btn.connect("clicked", lambda _: self._remove_item())
        edit_btn = Gtk.Button(label="Edit")
        edit_btn.connect("clicked", lambda _: self._edit_item())

        button_box.pack_start(add_group_btn, False, False, 0)
        button_box.pack_start(add_btn, False, False, 0)
        button_box.pack_start(edit_btn, False, False, 0)
        button_box.pack_start(remove_btn, False, False, 0)
        move_up_btn = Gtk.Button(label="Up")
        move_up_btn.connect("clicked", lambda _: self._move_item(-1))
        button_box.pack_start(move_up_btn, False, False, 0)
        move_down_btn = Gtk.Button(label="Down")
        move_down_btn.connect("clicked", lambda _: self._move_item(1))
        button_box.pack_start(move_down_btn, False, False, 0)

        box.pack_start(button_box, False, False, 0)

        self._load_bookmarks_tree()
        return box

    def _load_bookmarks_tree(self) -> None:
        self._bookmarks_store.clear()
        self._group_iters = {}
        self.bookmarks.walk_bookmarks(self._tree_group_callback, self._tree_bookmark_callback, None)

    def _get_folder_icon(self) -> GdkPixbuf.Pixbuf | None:
        if "folder" not in self._icon_cache:
            try:
                self._icon_cache["folder"] = Gtk.IconTheme.get_default().load_icon("folder", 16, 0)
            except:
                self._icon_cache["folder"] = None
        return self._icon_cache.get("folder")

    def _get_default_folder_icon(self) -> GdkPixbuf.Pixbuf | None:
        if "default_folder" not in self._icon_cache:
            winamp_path = self.bookmarks.filepath.parent / "icons" / "winamp.png"
            if winamp_path.exists():
                try:
                    self._icon_cache["default_folder"] = GdkPixbuf.Pixbuf.new_from_file_at_size(
                        str(winamp_path), 16, 16
                    )
                except:
                    pass
            if "default_folder" not in self._icon_cache:
                self._icon_cache["default_folder"] = self._get_folder_icon()
        return self._icon_cache.get("default_folder")

    def _get_radio_icon(self, station_name: str) -> GdkPixbuf.Pixbuf | None:
        if station_name in self._icon_cache:
            return self._icon_cache[station_name]

        icon_path = self.bookmarks.get_radio_icon(station_name)
        if icon_path and Path(icon_path).exists():
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, 16, 16)
                self._icon_cache[station_name] = pixbuf
                return pixbuf
            except Exception as e:
                self.logger.debug(f"Failed to load icon for {station_name}: {e}")

        try:
            default = Gtk.IconTheme.get_default().load_icon("audio-x-generic", 16, 0)
            self._icon_cache[station_name] = default
            return default
        except:
            return None

    def _tree_group_callback(self, group_name: str, parent) -> object:
        if group_name == "root":
            parent = None
        elif group_name not in self._group_iters:
            folder_icon = self._get_folder_icon()
            self._group_iters[group_name] = self._bookmarks_store.append(
                parent, [folder_icon, f"[{group_name}]", "group"]
            )
        return self._group_iters.get(group_name)

    def _tree_bookmark_callback(self, radio_name: str, parent) -> None:
        if radio_name.startswith("["):
            return
        icon = self._get_radio_icon(radio_name)
        self._bookmarks_store.append(parent, [icon, radio_name, "station"])

    def _move_item(self, direction: int) -> None:
        model, iter_selected = self._get_selected_iter()
        if not iter_selected:
            return

        if direction > 0:
            sibling = model.iter_next(iter_selected)
            if sibling:
                model.move_after(iter_selected, sibling)
                self._tree_view.get_selection().select_iter(iter_selected)
        else:
            path = model.get_path(iter_selected)
            indices = path.get_indices()
            if len(indices) == 1:
                if indices[0] > 0:
                    sibling_path = (indices[0] - 1,)
                    sibling = model.get_iter(sibling_path)
                    if sibling:
                        model.move_before(iter_selected, sibling)
                        self._tree_view.get_selection().select_iter(iter_selected)
            else:
                parent = model.iter_parent(iter_selected)
                parent_path = model.get_path(parent)
                parent_indices = parent_path.get_indices()
                child_index = indices[-1]
                if child_index > 0:
                    sibling_path = tuple(parent_indices + [child_index - 1])
                    sibling = model.get_iter(sibling_path)
                    if sibling:
                        model.move_before(iter_selected, sibling)
                        self._tree_view.get_selection().select_iter(iter_selected)

    def _get_selected_iter(self):
        selection = self._tree_view.get_selection()
        model, iter_selected = selection.get_selected()
        return model, iter_selected

    def _on_row_activated(self, tree_view, path, column):
        model = tree_view.get_model()
        iter_selected = model.get_iter(path)
        item_type = model.get_value(iter_selected, 2)
        if item_type == "station":
            station_name = model.get_value(iter_selected, 1)
            self.mediator.play(station_name)

    def _import_icon_from_file(self) -> str | None:
        dialog = Gtk.FileChooserDialog(
            title="Select Icon Image",
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Open", Gtk.ResponseType.OK)

        filter_text = Gtk.FileFilter()
        filter_text.set_name("Images")
        filter_text.add_mime_type("image/png")
        filter_text.add_mime_type("image/jpeg")
        filter_text.add_mime_type("image/gif")
        filter_text.add_mime_type("image/webp")
        filter_text.add_mime_type("image/svg+xml")
        dialog.add_filter(filter_text)

        response = dialog.run()
        file_path = None

        if response == Gtk.ResponseType.OK:
            file_path = dialog.get_filename()
        dialog.destroy()

        if not file_path:
            return None

        return self._save_icon_from_source(file_path)

    def _import_icon_from_url(self) -> str | None:
        dialog = Gtk.MessageDialog(
            transient_for=None,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Enter Icon URL",
        )

        entry = Gtk.Entry()
        entry.set_width_chars(50)
        entry.set_placeholder_text("https://example.com/icon.png")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        box.pack_start(Gtk.Label(label="Enter image URL:"), False, False, 0)
        box.pack_start(entry, False, False, 0)
        dialog.get_content_area().pack_start(box, True, True, 0)
        dialog.show_all()

        response = dialog.run()
        url = entry.get_text().strip() if response == Gtk.ResponseType.OK else None
        dialog.destroy()

        if not url:
            return None

        return self._save_icon_from_source(url)

    def _save_icon_from_source(self, source: str) -> str | None:
        import hashlib
        import requests
        import urllib.parse

        try:
            icons_dir = self.bookmarks.filepath.parent / "icons"
            icons_dir.mkdir(parents=True, exist_ok=True)

            if source.startswith("http://") or source.startswith("https://"):
                response = requests.get(source, timeout=10)
                if response.status_code != 200:
                    return None
                image_data = response.content
                ext = self._get_extension_from_content_type(
                    response.headers.get("content-type", "")
                )
                if not ext:
                    ext = self._guess_extension_from_content(image_data)
            else:
                with open(source, "rb") as f:
                    image_data = f.read()
                ext = Path(source).suffix.lower()
                if ext not in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico"]:
                    ext = self._guess_extension_from_content(image_data)

            if not ext:
                ext = ".png"

            hash_name = hashlib.md5(image_data).hexdigest()[:12]
            icon_path = icons_dir / f"custom_{hash_name}{ext}"

            with open(icon_path, "wb") as f:
                f.write(image_data)

            if ext != ".png":
                png_path = icon_path.with_suffix(".png")
                if self._convert_to_png(icon_path, png_path):
                    icon_path.unlink()
                    icon_path = png_path

            return str(icon_path)

        except Exception as e:
            self.logger.error(f"Failed to save icon: {e}")
            return None

    def _get_extension_from_content_type(self, content_type: str) -> str | None:
        mapping = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/svg+xml": ".svg",
            "image/x-icon": ".ico",
            "image/vnd.microsoft.icon": ".ico",
        }
        return mapping.get(content_type.lower())

    def _guess_extension_from_content(self, data: bytes) -> str | None:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return ".png"
        elif data[:2] in [b"\xff\xd8", b"\xff\xdf"]:
            return ".jpg"
        elif data[:6] in [b"GIF87a", b"GIF89a"]:
            return ".gif"
        elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return ".webp"
        elif data[:5] == b"<svg " or data[:4] == b"<svg":
            return ".svg"
        elif data[:2] == b"\x00\x00" or data[:4] in [b"\x00\x00\x01\x00", b"\x00\x00\x02\x00"]:
            return ".ico"
        return None

    def _convert_to_png(self, src_path: Path, dst_path: Path) -> bool:
        try:
            loader = GdkPixbuf.PixbufLoader()
            with open(src_path, "rb") as f:
                loader.write(f.read())
            loader.close()
            pixbuf = loader.get_pixbuf()
            pixbuf.savev(str(dst_path), "png", [], [])
            return True
        except Exception as e:
            self.logger.error(f"Failed to convert to PNG: {e}")
            return False

    def _on_icon_select(
        self, dialog, entry, icon_preview, item_name, item_type, current_icon, source
    ):
        icon_path = None
        if source == "file":
            icon_path = self._import_icon_from_file()
        else:
            icon_path = self._import_icon_from_url()

        if icon_path and Path(icon_path).exists():
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, 32, 32)
                icon_preview.set_from_pixbuf(pb)
                icon_preview.current_icon = icon_path
            except Exception as e:
                self.logger.error(f"Failed to load icon: {e}")
                icon_preview.set_from_icon_name("image-missing", 5)

    def _on_icon_remove(self, entry, icon_preview, item_name, item_type):
        icon_preview.set_from_icon_name("image-missing", 5)
        icon_preview.current_icon = None
        name = item_name.strip("[]") if item_type == "group" else item_name
        if item_type == "group":
            self.bookmarks.set_group_icon(name, "")
        else:
            self.bookmarks.set_radio_icon(name, "")

    def _add_group(self) -> None:
        from gi.repository import Gtk

        dialog = Gtk.MessageDialog(
            transient_for=None,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Add Group",
        )

        entry = Gtk.Entry()
        entry.set_width_chars(30)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        box.pack_start(Gtk.Label(label="Group Name:"), False, False, 0)
        box.pack_start(entry, False, False, 0)
        dialog.get_content_area().pack_start(box, True, True, 0)
        dialog.show_all()

        if dialog.run() == Gtk.ResponseType.OK:
            name = entry.get_text().strip()
            if name:
                self.bookmarks.add_group(name)
                self._load_bookmarks_tree()

        dialog.destroy()

    def _add_station(self) -> None:
        from gi.repository import Gtk

        model, iter_selected = self._get_selected_iter()
        parent = None
        group_name = "root"

        if iter_selected:
            path = model.get_path(iter_selected)
            if model.iter_has_child(iter_selected):
                parent = iter_selected
                group_name = model.get_value(iter_selected, 1).strip("[]")
            else:
                parent = model.iter_parent(iter_selected)
                if parent:
                    group_name = model.get_value(parent, 1).strip("[]")

        dialog = Gtk.MessageDialog(
            transient_for=None,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Add Station",
        )

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

        name_entry = Gtk.Entry()
        name_entry.set_width_chars(40)
        name_label = Gtk.Label(label="Name:")
        name_label.set_width_chars(8)
        name_label.set_alignment(0, 0.5)
        name_box = Gtk.Box()
        name_box.pack_start(name_label, False, False, 0)
        name_box.pack_start(name_entry, True, True, 0)

        url_entry = Gtk.Entry()
        url_entry.set_width_chars(40)
        url_label = Gtk.Label(label="URL:")
        url_label.set_width_chars(8)
        url_label.set_alignment(0, 0.5)
        url_box = Gtk.Box()
        url_box.pack_start(url_label, False, False, 0)
        url_box.pack_start(url_entry, True, True, 0)

        box.pack_start(name_box, False, False, 0)
        box.pack_start(url_box, False, False, 0)
        dialog.get_content_area().pack_start(box, True, True, 0)
        dialog.show_all()

        if dialog.run() == Gtk.ResponseType.OK:
            name = name_entry.get_text().strip()
            url = url_entry.get_text().strip()
            if name and url:
                self.bookmarks.add_radio(name, url, group_name)
                self.favicon_grabber.grab_favicon_async(url, self._on_favicon_grabbed)
                self._load_bookmarks_tree()

        dialog.destroy()

    def _on_favicon_grabbed(self, icon_path: Path) -> None:
        pass

    def _remove_item(self) -> None:
        model, iter_selected = self._get_selected_iter()
        if not iter_selected:
            return

        item_type = model.get_value(iter_selected, 2)
        item_name = model.get_value(iter_selected, 1)

        if item_type == "group":
            group_name = item_name.strip("[]")
            self.bookmarks.remove_group(group_name)
        else:
            self.bookmarks.remove_radio(item_name)

        self._load_bookmarks_tree()

    def _edit_item(self) -> None:
        from gi.repository import Gtk

        model, iter_selected = self._get_selected_iter()
        if not iter_selected:
            return

        item_type = model.get_value(iter_selected, 2)
        item_name = model.get_value(iter_selected, 1)
        current_icon = (
            self.bookmarks.get_group_icon(item_name.strip("[]"))
            if item_type == "group"
            else self.bookmarks.get_radio_icon(item_name)
        )

        if item_type == "group":
            dialog = Gtk.MessageDialog(
                transient_for=None,
                flags=0,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.OK_CANCEL,
                text="Edit Group",
            )
            entry = Gtk.Entry()
            entry.set_text(item_name.strip("[]"))
            entry.set_width_chars(30)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            box.pack_start(Gtk.Label(label="Group Name:"), False, False, 0)
            box.pack_start(entry, False, False, 0)

            icon_box = Gtk.Box(spacing=5)
            icon_preview = Gtk.Image()
            if current_icon and Path(current_icon).exists():
                try:
                    pb = GdkPixbuf.Pixbuf.new_from_file_at_size(current_icon, 32, 32)
                    icon_preview.set_from_pixbuf(pb)
                except:
                    icon_preview.set_from_icon_name("image-missing", 5)
            else:
                icon_preview.set_from_icon_name("image-missing", 5)

            icon_btn_box = Gtk.Box(spacing=5)
            btn_file = Gtk.Button(label="From File")
            btn_url = Gtk.Button(label="From URL")
            btn_remove = Gtk.Button(label="Remove")
            btn_file.connect(
                "clicked",
                lambda _: self._on_icon_select(
                    dialog, entry, icon_preview, item_name, item_type, current_icon, "file"
                ),
            )
            btn_url.connect(
                "clicked",
                lambda _: self._on_icon_select(
                    dialog, entry, icon_preview, item_name, item_type, current_icon, "url"
                ),
            )
            btn_remove.connect(
                "clicked", lambda _: self._on_icon_remove(entry, icon_preview, item_name, item_type)
            )
            icon_btn_box.pack_start(btn_file, False, False, 0)
            icon_btn_box.pack_start(btn_url, False, False, 0)
            icon_btn_box.pack_start(btn_remove, False, False, 0)

            box.pack_start(Gtk.Label(label="Icon:"), False, False, 0)
            box.pack_start(icon_preview, False, False, 0)
            box.pack_start(icon_btn_box, False, False, 0)

            dialog.get_content_area().pack_start(box, True, True, 0)
            dialog.show_all()

            icon_ref = {"path": current_icon}

            def on_icon_select_local(source, img, ref):
                icon_path = None
                if source == "file":
                    icon_path = self._import_icon_from_file()
                else:
                    icon_path = self._import_icon_from_url()

                if icon_path and Path(icon_path).exists():
                    ref["path"] = icon_path
                    try:
                        pb = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, 32, 32)
                        img.set_from_pixbuf(pb)
                    except:
                        img.set_from_icon_name("image-missing", 5)

            def on_icon_remove_local(img, ref, name, is_group):
                ref["path"] = None
                img.set_from_icon_name("image-missing", 5)
                if is_group:
                    self.bookmarks.set_group_icon(name, "")
                else:
                    self.bookmarks.set_radio_icon(name, "")

            btn_file.disconnect_by_func(
                lambda _: self._on_icon_select(
                    dialog, entry, icon_preview, item_name, item_type, current_icon, "file"
                )
            )
            btn_url.disconnect_by_func(
                lambda _: self._on_icon_select(
                    dialog, entry, icon_preview, item_name, item_type, current_icon, "url"
                )
            )
            btn_remove.disconnect_by_func(
                lambda _: self._on_icon_remove(entry, icon_preview, item_name, item_type)
            )
            btn_file.connect(
                "clicked", lambda _: on_icon_select_local("file", icon_preview, icon_ref)
            )
            btn_url.connect(
                "clicked", lambda _: on_icon_select_local("url", icon_preview, icon_ref)
            )
            btn_remove.connect(
                "clicked",
                lambda _: on_icon_remove_local(icon_preview, icon_ref, item_name.strip("[]"), True),
            )

            if dialog.run() == Gtk.ResponseType.OK:
                new_name = entry.get_text().strip()
                if new_name:
                    self.bookmarks.rename_group(item_name.strip("[]"), new_name)
                    if icon_ref["path"]:
                        self.bookmarks.set_group_icon(new_name, icon_ref["path"])
                    self._load_bookmarks_tree()
            dialog.destroy()
        else:
            parent = model.iter_parent(iter_selected)
            group_name = "root"
            if parent:
                group_name = model.get_value(parent, 1).strip("[]")

            old_url = self.bookmarks.get_radio_url(item_name) or ""
            current_icon = self.bookmarks.get_radio_icon(item_name)

            dialog = Gtk.MessageDialog(
                transient_for=None,
                flags=0,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.OK_CANCEL,
                text="Edit Station",
            )

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

            name_entry = Gtk.Entry()
            name_entry.set_text(item_name)
            name_entry.set_width_chars(40)
            name_label = Gtk.Label(label="Name:")
            name_label.set_width_chars(8)
            name_label.set_alignment(0, 0.5)
            name_box = Gtk.Box()
            name_box.pack_start(name_label, False, False, 0)
            name_box.pack_start(name_entry, True, True, 0)

            url_entry = Gtk.Entry()
            url_entry.set_text(old_url)
            url_entry.set_width_chars(40)
            url_label = Gtk.Label(label="URL:")
            url_label.set_width_chars(8)
            url_label.set_alignment(0, 0.5)
            url_box = Gtk.Box()
            url_box.pack_start(url_label, False, False, 0)
            url_box.pack_start(url_entry, True, True, 0)

            icon_box = Gtk.Box(spacing=5)
            icon_preview = Gtk.Image()
            if current_icon and Path(current_icon).exists():
                try:
                    pb = GdkPixbuf.Pixbuf.new_from_file_at_size(current_icon, 32, 32)
                    icon_preview.set_from_pixbuf(pb)
                except:
                    icon_preview.set_from_icon_name("image-missing", 5)
            else:
                icon_preview.set_from_icon_name("image-missing", 5)

            icon_btn_box = Gtk.Box(spacing=5)
            btn_file = Gtk.Button(label="From File")
            btn_url = Gtk.Button(label="From URL")
            btn_remove = Gtk.Button(label="Remove")
            btn_file.connect(
                "clicked",
                lambda _: self._on_icon_select(
                    dialog, name_entry, icon_preview, item_name, item_type, current_icon, "file"
                ),
            )
            btn_url.connect(
                "clicked",
                lambda _: self._on_icon_select(
                    dialog, name_entry, icon_preview, item_name, item_type, current_icon, "url"
                ),
            )
            btn_remove.connect(
                "clicked",
                lambda _: self._on_icon_remove(name_entry, icon_preview, item_name, item_type),
            )
            icon_btn_box.pack_start(btn_file, False, False, 0)
            icon_btn_box.pack_start(btn_url, False, False, 0)
            icon_btn_box.pack_start(btn_remove, False, False, 0)

            box.pack_start(name_box, False, False, 0)
            box.pack_start(url_box, False, False, 0)
            box.pack_start(Gtk.Separator(), False, False, 5)
            box.pack_start(Gtk.Label(label="Icon:"), False, False, 0)
            box.pack_start(icon_preview, False, False, 0)
            box.pack_start(icon_btn_box, False, False, 0)
            dialog.get_content_area().pack_start(box, True, True, 0)
            dialog.show_all()

            icon_ref = [current_icon]

            if dialog.run() == Gtk.ResponseType.OK:
                new_name = name_entry.get_text().strip()
                new_url = url_entry.get_text().strip()
                if new_name and new_url:
                    self.bookmarks.remove_radio(item_name)
                    self.bookmarks.add_radio(new_name, new_url, group_name)
                    if icon_ref[0] and icon_ref[0] != current_icon:
                        self.bookmarks.set_radio_icon(new_name, icon_ref[0])
                    elif new_url != old_url:
                        self.favicon_grabber.grab_favicon_async(new_url, self._on_favicon_grabbed)
                    self._load_bookmarks_tree()

            dialog.destroy()

    def _on_quit(self, _widget: Gtk.Widget) -> None:
        self.logger.info("Quitting")
        if self.mediator and self.mediator.player:
            self.mediator.player.stop()
        import os

        Gtk.main_quit()
        os._exit(0)

    def _on_about(self, _widget: Gtk.Widget) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=None,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=f"{APP_NAME}",
        )
        dialog.format_secondary_markup("A modern radio streaming player for linux\n\nVersion 0.7.5")
        dialog.run()
        dialog.destroy()

    def _on_reload_bookmarks(self, _widget: Gtk.Widget) -> None:
        self.bookmarks.load()
        self._update_radios_menu()
        self.event_manager.notify(self.event_manager.BOOKMARKS_RELOADED)

    def _on_bookmarks_reloaded(self, data: dict) -> None:
        self.logger.info("Bookmarks reloaded - refreshing menus")
        self.bookmarks.load()
        self._icon_cache.clear()
        self._load_bookmarks_tree()
        self._update_radios_menu()

    def _on_save_bookmarks(self) -> None:
        self.bookmarks.rebuild_from_tree(self._bookmarks_store)
        self.bookmarks.load()
        self._update_radios_menu()
        self.event_manager.notify(self.event_manager.BOOKMARKS_RELOADED)

    def _on_plugin_preferences(self, _widget: Gtk.Widget) -> None:
        self.logger.info("Opening plugin configuration")

        dialog = Gtk.Dialog(
            title="Plugin Configuration",
            flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
        )
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(450, 400)

        content = dialog.get_content_area()
        content.set_spacing(10)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)

        store = Gtk.ListStore(bool, str, str, str)
        tree = Gtk.TreeView(model=store)

        renderer_toggle = Gtk.CellRendererToggle()
        renderer_toggle.connect("toggled", self._on_plugin_toggled, store)
        col_toggle = Gtk.TreeViewColumn("Enabled", renderer_toggle, active=0)
        tree.append_column(col_toggle)

        renderer = Gtk.CellRendererText()
        col_name = Gtk.TreeViewColumn("Plugin", renderer, text=1)
        tree.append_column(col_name)

        col_desc = Gtk.TreeViewColumn("Description", renderer, text=2)
        tree.append_column(col_desc)

        scroll.add(tree)
        content.pack_start(scroll, True, True, 0)

        self._plugin_store = store
        self._plugin_toggle = renderer_toggle

        if self.plugin_manager:
            active_plugins = self.settings.get_list("active_plugins")
            for info in self.plugin_manager.get_plugins():
                is_active = info.name in active_plugins
                store.append([is_active, info.name, info.description, info.author])

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def _on_plugin_toggled(
        self, cell: Gtk.CellRendererToggle, path: str, store: Gtk.ListStore
    ) -> None:
        if not self.plugin_manager:
            return

        iter = store.get_iter(path)
        if iter:
            current = store.get_value(iter, 0)
            store.set_value(iter, 0, not current)

            plugin_name = store.get_value(iter, 1)
            active_plugins = self.settings.get_list("active_plugins")

            if not current:
                if plugin_name not in active_plugins:
                    active_plugins.append(plugin_name)
                    self.plugin_manager.activate_plugin(plugin_name)
                    self.logger.info(f"Activated plugin: {plugin_name}")
            else:
                if plugin_name in active_plugins:
                    active_plugins.remove(plugin_name)
                    self.plugin_manager.deactivate_plugin(plugin_name)
                    self.logger.info(f"Deactivated plugin: {plugin_name}")

            self.settings.set_list("active_plugins", active_plugins)
            self.settings.save()

            self._populate_plugin_menu()

    def _on_state_changed(self, data: dict) -> None:
        state = data.get("state", "stopped")
        station = data.get("station", "")

        if state == "playing":
            self.turn_on_off.set_label(f'Turn Off "{station}"')
            self.turn_on_off.set_sensitive(True)
            self.turn_on_off2.set_label(f'Turn Off "{station}"')
            self.turn_on_off2.set_sensitive(True)
            self.icon.set_from_file(str(ICON_ON))

        elif state == "stopped":
            if self.mediator.context.station:
                self.turn_on_off.set_label(f'Turn On "{self.mediator.context.station}"')
                self.turn_on_off.set_sensitive(True)
                self.turn_on_off2.set_label(f'Turn On "{self.mediator.context.station}"')
                self.turn_on_off2.set_sensitive(True)
            else:
                self.turn_on_off.set_label("Turned Off")
                self.turn_on_off.set_sensitive(False)
                self.turn_on_off2.set_label("Turned Off")
                self.turn_on_off2.set_sensitive(False)
            self.icon.set_from_file(str(ICON_OFF))

        elif state == "paused":
            if not self.mediator.context.station:
                self.turn_on_off.set_label("Turned Off")
                self.turn_on_off.set_sensitive(False)
                self.turn_on_off2.set_label("Turned Off")
                self.turn_on_off2.set_sensitive(False)
            else:
                self.turn_on_off.set_label(f'Turn On "{self.mediator.context.station}"')
                self.turn_on_off.set_sensitive(True)
                self.turn_on_off2.set_label(f'Turn On "{self.mediator.context.station}"')
                self.turn_on_off2.set_sensitive(True)
            self.icon.set_from_file(str(ICON_OFF))

        elif state == "connecting":
            self.turn_on_off.set_sensitive(True)
            self.turn_on_off.set_label(f'Turn Off "{station}"')
            self.turn_on_off2.set_sensitive(True)
            self.icon.set_tooltip_markup(f"Connecting to {html.escape(station)}")
            self.icon.set_from_file(str(ICON_CONNECTING))

        self.icon.set_tooltip_markup(self._get_tooltip_text())

    def _on_song_changed(self, data: dict) -> None:
        self.icon.set_tooltip_markup(self._get_tooltip_text())

    def _on_volume_changed(self, data: dict) -> None:
        self.icon.set_tooltip_markup(self._get_tooltip_text())

    def _get_tooltip_text(self) -> str:
        radio = html.escape(self.mediator.context.station or "")
        volume = self.mediator.context.get_volume_percent()

        if self.mediator.context.state.value == "playing":
            title = html.escape(self.mediator.context.title or "")
            artist = html.escape(self.mediator.context.artist or "")

            if title or artist:
                if artist:
                    song_info = f"{artist} - {title}" if title else artist
                else:
                    song_info = title
                return f"Playing <b>{radio}</b> (vol: {volume}%)\n<i>{song_info}</i>"
            else:
                return f"Playing <b>{radio}</b> (vol: {volume}%)"
        elif self.mediator.context.state.value == "connecting":
            return f"Connecting to <b>{radio}</b>..."
        else:
            return f"Idle (vol: {volume}%)"

    def get_plugin_menu(self) -> Gtk.Menu:
        return self.plugin_menu

    def run(self) -> None:
        self.build_menu()
        Gtk.main()

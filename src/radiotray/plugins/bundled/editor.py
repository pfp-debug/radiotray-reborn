import logging
from pathlib import Path
from typing import TYPE_CHECKING

from gi.repository import Gtk, Gdk, GdkPixbuf

from radiotray.plugins.base import Plugin

if TYPE_CHECKING:
    from radiotray.events.manager import EventManager
    from radiotray.config.bookmarks import BookmarkManager
    from radiotray.config.settings import SettingsManager
    from radiotray.core.mediator import StateMediator


class EditorPlugin(Plugin):
    NAME = "Editor"
    DESCRIPTION = "Bookmarks Editor - Configure radio stations and groups"

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._icon_cache = {}

    def activate(self) -> None:
        self.logger.info("Editor plugin activated")
        self._active = True

    def get_menu_item(self) -> Gtk.MenuItem | None:
        menu_item = Gtk.MenuItem(label="Open Editor...")
        menu_item.connect("activate", self._on_open_editor)
        return menu_item

    def _on_open_editor(self, _widget=None) -> None:
        self._open_editor()

    def _open_editor(self) -> None:
        dialog = Gtk.Dialog(
            title="Radio Station Editor",
            flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
        )
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(600, 500)

        notebook = Gtk.Notebook()
        dialog.vbox.pack_start(notebook, True, True, 0)

        bookmarks_page = self._create_bookmarks_page(dialog)
        notebook.append_page(bookmarks_page, Gtk.Label(label="Bookmarks"))

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def _create_bookmarks_page(self, parent_dialog: Gtk.Dialog) -> Gtk.Box:
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
        up_btn = Gtk.Button(label="Up")
        up_btn.connect("clicked", lambda _: self._move_up())
        down_btn = Gtk.Button(label="Down")
        down_btn.connect("clicked", lambda _: self._move_down())
        save_btn = Gtk.Button(label="Save")
        save_btn.connect("clicked", lambda _: self._save_bookmarks())

        button_box.pack_start(add_group_btn, False, False, 0)
        button_box.pack_start(add_btn, False, False, 0)
        button_box.pack_start(edit_btn, False, False, 0)
        button_box.pack_start(up_btn, False, False, 0)
        button_box.pack_start(down_btn, False, False, 0)
        button_box.pack_start(remove_btn, False, False, 0)
        button_box.pack_start(save_btn, False, False, 0)

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
            return None
        elif group_name not in self._group_iters:
            folder_icon = self._get_folder_icon()
            group_icon = self.bookmarks.get_group_icon(group_name)
            if group_icon and Path(group_icon).exists():
                try:
                    folder_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(group_icon, 16, 16)
                except:
                    pass
            iter_val = self._bookmarks_store.append(
                parent, [folder_icon, f"[{group_name}]", "group"]
            )
            self._group_iters[group_name] = iter_val
            return iter_val
        return self._group_iters[group_name]

    def _tree_bookmark_callback(self, radio_name: str, parent) -> None:
        icon = self._get_radio_icon(radio_name)
        self._bookmarks_store.append(parent, [icon, radio_name, "station"])

    def _move_up(self) -> None:
        selection = self._tree_view.get_selection()
        model, iter_selected = selection.get_selected()
        if not iter_selected:
            return
        path = model.get_path(iter_selected)
        indices = path.get_indices()
        if indices[0] == 0:
            return
        prev_path = path.copy()
        prev_path.prev()
        prev_iter = model.get_iter(prev_path)
        model.swap(iter_selected, prev_iter)
        selection.unselect_all()
        selection.select_path(prev_path)
        self._tree_view.set_cursor(prev_path, start_editing=False)
        self._tree_view.scroll_to_cell(prev_path, None, True, 0.5, 0)

    def _move_down(self) -> None:
        selection = self._tree_view.get_selection()
        model, iter_selected = selection.get_selected()
        if not iter_selected:
            return
        next_iter = model.iter_next(iter_selected)
        if not next_iter:
            return
        path = model.get_path(iter_selected)
        new_path = path.copy()
        new_path.next()
        model.swap(iter_selected, next_iter)
        selection.unselect_all()
        selection.select_path(new_path)
        self._tree_view.set_cursor(new_path, start_editing=False)
        self._tree_view.scroll_to_cell(new_path, None, True, 0.5, 0)

    def _get_selected_iter(self):
        selection = self._tree_view.get_selection()
        model, iter_selected = selection.get_selected()
        return model, iter_selected

    def _on_row_activated(self, tree, path, col):
        model = tree.get_model()
        iter_selected = model.get_iter(path)
        item_type = model.get_value(iter_selected, 2)
        if item_type == "station":
            station_name = model.get_value(iter_selected, 1)
            self.mediator.play(station_name)

    def _add_group(self) -> None:
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
        model, iter_selected = self._get_selected_iter()
        group_name = "root"
        if iter_selected:
            item_type = model.get_value(iter_selected, 2)
            if item_type == "group":
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
                self._load_bookmarks_tree()

        dialog.destroy()

    def _remove_item(self) -> None:
        model, iter_selected = self._get_selected_iter()
        if not iter_selected:
            return

        item_type = model.get_value(iter_selected, 2)
        item_name = model.get_value(iter_selected, 1)

        parent = model.iter_parent(iter_selected)
        prev_sibling = model.iter_previous(iter_selected)
        next_sibling = model.iter_next(iter_selected)

        select_path = None
        if prev_sibling:
            select_path = model.get_path(prev_sibling)
        elif next_sibling:
            select_path = model.get_path(next_sibling)
        elif parent:
            select_path = model.get_path(parent)

        if item_type == "group":
            group_name = item_name.strip("[]")
            self.bookmarks.remove_group(group_name)
        else:
            self.bookmarks.remove_radio(item_name)

        self._load_bookmarks_tree()

        if select_path:
            try:
                selection = self._tree_view.get_selection()
                selection.unselect_all()
                selection.select_path(select_path)
                self._tree_view.set_cursor(select_path, start_editing=False)
                self._tree_view.scroll_to_cell(select_path, None, True, 0.5, 0)
            except:
                pass

    def _edit_item(self) -> None:
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
            self._edit_group(item_name, current_icon)
        else:
            parent = model.iter_parent(iter_selected)
            group_name = "root"
            if parent:
                group_name = model.get_value(parent, 1).strip("[]")
            self._edit_station(item_name, group_name, current_icon)

    def _edit_group(self, item_name: str, current_icon: str) -> None:
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
        icon_btn_box.pack_start(btn_file, False, False, 0)
        icon_btn_box.pack_start(btn_url, False, False, 0)
        icon_btn_box.pack_start(btn_remove, False, False, 0)

        box.pack_start(Gtk.Label(label="Icon:"), False, False, 0)
        box.pack_start(icon_preview, False, False, 0)
        box.pack_start(icon_btn_box, False, False, 0)

        icon_ref = {"path": current_icon}

        def on_icon_select(source):
            icon_path = None
            if source == "file":
                icon_path = self._import_icon_from_file()
            else:
                icon_path = self._import_icon_from_url()
            if icon_path and Path(icon_path).exists():
                icon_ref["path"] = icon_path
                try:
                    pb = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, 32, 32)
                    icon_preview.set_from_pixbuf(pb)
                except:
                    icon_preview.set_from_icon_name("image-missing", 5)

        def on_icon_remove():
            icon_ref["path"] = None
            icon_preview.set_from_icon_name("image-missing", 5)

        btn_file.connect("clicked", lambda _: on_icon_select("file"))
        btn_url.connect("clicked", lambda _: on_icon_select("url"))
        btn_remove.connect("clicked", lambda _: on_icon_remove())

        dialog.get_content_area().pack_start(box, True, True, 0)
        dialog.show_all()

        if dialog.run() == Gtk.ResponseType.OK:
            new_name = entry.get_text().strip()
            if new_name:
                self.bookmarks.rename_group(item_name.strip("[]"), new_name)
                if icon_ref["path"]:
                    self.bookmarks.set_group_icon(new_name, icon_ref["path"])
                self._load_bookmarks_tree()
        dialog.destroy()

    def _edit_station(self, item_name: str, group_name: str, current_icon: str) -> None:
        old_url = self.bookmarks.get_radio_url(item_name) or ""

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

        icon_ref = {"path": current_icon}

        def on_icon_select(source):
            icon_path = None
            if source == "file":
                icon_path = self._import_icon_from_file()
            else:
                icon_path = self._import_icon_from_url()
            if icon_path and Path(icon_path).exists():
                icon_ref["path"] = icon_path
                try:
                    pb = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, 32, 32)
                    icon_preview.set_from_pixbuf(pb)
                except:
                    icon_preview.set_from_icon_name("image-missing", 5)

        def on_icon_remove():
            icon_ref["path"] = None
            icon_preview.set_from_icon_name("image-missing", 5)

        btn_file.connect("clicked", lambda _: on_icon_select("file"))
        btn_url.connect("clicked", lambda _: on_icon_select("url"))
        btn_remove.connect("clicked", lambda _: on_icon_remove())

        if dialog.run() == Gtk.ResponseType.OK:
            new_name = name_entry.get_text().strip()
            new_url = url_entry.get_text().strip()
            if new_name and new_url:
                self.bookmarks.remove_radio(item_name)
                self.bookmarks.add_radio(new_name, new_url, group_name)
                if icon_ref["path"]:
                    self.bookmarks.set_radio_icon(new_name, icon_ref["path"])
                self._load_bookmarks_tree()

        dialog.destroy()

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

    def _save_bookmarks(self) -> None:
        self.bookmarks.rebuild_from_tree(self._bookmarks_store)
        self.bookmarks.load()
        self.event_manager.notify(self.event_manager.BOOKMARKS_RELOADED)

from lxml import etree
from pathlib import Path
import logging
import traceback
import shutil
from datetime import datetime


class BookmarkManager:
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.root: etree._Element | None = None
        self.logger = logging.getLogger(__name__)

    def load(self) -> None:
        self.logger.info(f"Loading bookmarks from {self.filepath}")
        self.logger.info(f"LOAD CALL STACK:\n{''.join(traceback.format_stack())}")
        parser = etree.XMLParser(remove_blank_text=True)
        self.root = etree.parse(str(self.filepath), parser).getroot()
        if self.root is None:
            raise ValueError(f"Failed to parse bookmarks from {self.filepath}")
        group_root = self.root.xpath("//group[@name='root']")
        if len(group_root) == 0:
            new_group = etree.Element("group")
            new_group.set("name", "root")
            for child in list(self.root):
                self.root.remove(child)
                new_group.append(child)
            self.root.append(new_group)
            self.save()
        self.logger.debug("Bookmarks loaded successfully")

    def save(self) -> None:
        self.logger.info(f"Saving bookmarks to {self.filepath}")
        self.logger.info(f"SAVE CALL STACK:\n{''.join(traceback.format_stack())}")
        if self.filepath.exists():
            backup_path = (
                self.filepath.parent
                / f"bookmarks.xml.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            shutil.copy2(self.filepath, backup_path)
            self.logger.info(f"Backed up current bookmarks to {backup_path}")

            backups = sorted(
                self.filepath.parent.glob("bookmarks.xml.backup_*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if len(backups) > 3:
                for old_backup in backups[3:]:
                    old_backup.unlink()
                    self.logger.info(f"Removed old backup: {old_backup}")

        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, "wb") as f:
            f.write(
                etree.tostring(self.root, encoding="UTF-8", pretty_print=True, xml_declaration=True)
            )

    def list_radio_names(self) -> list[str]:
        return [
            str(a)
            for a in self.root.xpath("//bookmark/@name")
            if not str(a).startswith("[separator")
        ]

    def list_group_names(self) -> list[str]:
        return [str(g) for g in self.root.xpath("//group/@name")]

    def get_group_icon(self, name: str) -> str | None:
        result = self.root.xpath("//group[@name=$name]/@icon", name=name)
        return str(result[0]) if result else None

    def set_group_icon(self, name: str, icon_path: str) -> bool:
        group = self._get_group(name)
        if group is not None:
            group.set("icon", icon_path)
            self.save()
            return True
        return False

    def get_radio_url(self, name: str) -> str | None:
        result = self.root.xpath("//bookmark[@name=$name]/@url", name=name)
        return str(result[0]) if result else None

    def get_radio_icon(self, name: str) -> str | None:
        result = self.root.xpath("//bookmark[@name=$name]/@icon", name=name)
        return str(result[0]) if result else None

    def set_radio_icon(self, name: str, icon_path: str) -> bool:
        radio = self._get_radio(name)
        if radio is not None:
            radio.set("icon", icon_path)
            self.save()
            return True
        return False

    def add_group(self, name: str, parent: str = "root") -> bool:
        if parent == "root":
            parent_group = self.root.xpath("//group[@name='root']")
            if not parent_group:
                self.logger.error("Root group not found")
                return False
        else:
            parent_group = self.root.xpath("//group[@name=$name]", name=parent)
            if not parent_group:
                self.logger.error(f"Parent group '{parent}' not found")
                return False
        existing = self.root.xpath("//group[@name=$name]", name=name)
        if existing:
            self.logger.warning(f"Group '{name}' already exists")
            return False
        new_group = etree.SubElement(parent_group[0], "group")
        new_group.set("name", name)
        self.save()
        return True

    def remove_group(self, name: str) -> bool:
        group = self._get_group(name)
        if group is not None:
            group.getparent().remove(group)
            self.save()
            return True
        return False

    def rename_group(self, old_name: str, new_name: str) -> bool:
        group = self._get_group(old_name)
        if group is not None:
            group.set("name", new_name)
            self.save()
            return True
        return False

    def add_radio(self, name: str, url: str, group: str = "root") -> bool:
        target_group = self.root.xpath("//group[@name=$name]", name=group)
        if not target_group:
            self.logger.error(f"Group '{group}' not found")
            return False
        if self._radio_exists(name):
            self.logger.warning(f"Radio '{name}' already exists")
            return False
        radio = etree.SubElement(target_group[0], "bookmark")
        radio.set("name", name)
        radio.set("url", url)
        self.save()
        return True

    def remove_radio(self, name: str) -> bool:
        radio = self._get_radio(name)
        if radio is not None:
            radio.getparent().remove(radio)
            self.save()
            return True
        group = self._get_group(name)
        if group is not None:
            group.getparent().remove(group)
            self.save()
            return True
        return False

    def _radio_exists(self, name: str) -> bool:
        return self._get_radio(name) is not None

    def _get_radio(self, name: str) -> etree._Element | None:
        result = self.root.xpath("//bookmark[@name=$name]", name=name)
        return result[0] if result else None

    def _get_group(self, name: str) -> etree._Element | None:
        result = self.root.xpath("//group[@name=$name]", name=name)
        return result[0] if result else None

    def walk_bookmarks(self, group_func, bookmark_func, user_data, xpath: str = ""):
        children = self.root.xpath(f"/bookmarks{xpath}/group | /bookmarks{xpath}/bookmark")
        for child in children:
            name = child.get("name")
            if name is None:
                continue
            if child.tag == "group":
                new_data = group_func(name, user_data)
                self.walk_bookmarks(
                    group_func, bookmark_func, new_data, xpath + f"/group[@name='{name}']"
                )
            else:
                bookmark_func(name, user_data)

    def rebuild_from_tree(self, tree_store) -> None:
        url_map = {}

        def collect_urls(children):
            for child in children:
                name = child.get("name")
                if name is None:
                    continue
                if child.tag == "bookmark":
                    url = child.get("url", "")
                    url_map[name] = url
                elif child.tag == "group":
                    collect_urls(child)

        original_root = self.root.xpath("//group[@name='root']")[0]
        collect_urls(list(original_root))

        for child in list(original_root):
            original_root.remove(child)

        def process_iter(parent_iter, xml_parent):
            child = tree_store.iter_children(parent_iter)
            while child:
                name = tree_store.get_value(child, 1)
                item_type = tree_store.get_value(child, 2)
                if item_type == "group":
                    group_name = name.strip("[]")
                    new_group = etree.SubElement(xml_parent, "group")
                    new_group.set("name", group_name)
                    process_iter(child, new_group)
                else:
                    url = url_map.get(name, "")
                    new_radio = etree.SubElement(xml_parent, "bookmark")
                    new_radio.set("name", name)
                    new_radio.set("url", url)
                child = tree_store.iter_next(child)

        process_iter(None, original_root)
        self.save()

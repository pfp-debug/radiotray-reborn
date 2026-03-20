from lxml import etree
from pathlib import Path
import logging


class SettingsManager:
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.root: etree._Element | None = None
        self.logger = logging.getLogger(__name__)

    def load(self) -> None:
        self.logger.info(f"Loading settings from {self.filepath}")
        parser = etree.XMLParser(remove_blank_text=True)
        self.root = etree.parse(str(self.filepath), parser).getroot()

    def save(self) -> None:
        self.logger.info(f"Saving settings to {self.filepath}")
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, "wb") as f:
            f.write(
                etree.tostring(self.root, encoding="UTF-8", pretty_print=True, xml_declaration=True)
            )

    def get(self, key: str, default: str | None = None) -> str | None:
        result = self.root.xpath(f"//option[@name='{key}']/@value")
        return str(result[0]) if result else default

    def set(self, key: str, value: str) -> None:
        existing = self.root.xpath(f"//option[@name='{key}']")
        if existing:
            existing[0].set("value", value)
        else:
            option = etree.SubElement(self.root, "option")
            option.set("name", key)
            option.set("value", value)
        self.save()

    def get_list(self, key: str) -> list[str]:
        result = self.root.xpath(f"//option[@name='{key}']/item")
        return [str(item.text) for item in result if item.text]

    def set_list(self, key: str, items: list[str]) -> None:
        existing = self.root.xpath(f"//option[@name='{key}']")
        if existing:
            existing[0].getparent().remove(existing[0])
        option = etree.SubElement(self.root, "option")
        option.set("name", key)
        for item in items:
            elem = etree.SubElement(option, "item")
            elem.text = item
        self.save()

    def get_volume(self) -> float:
        val = self.get("volume_level", "1.0")
        try:
            return float(val)
        except ValueError:
            return 1.0

    def set_volume(self, volume: float) -> None:
        self.set("volume_level", str(volume))

    def get_last_station(self) -> str | None:
        return self.get("last_station")

    def set_last_station(self, station: str) -> None:
        self.set("last_station", station)

    def get_volume_increment(self) -> float:
        val = self.get("volume_increment", "0.05")
        try:
            return float(val)
        except ValueError:
            return 0.05

    def get_buffer_size(self) -> int:
        val = self.get("buffer_size", "0")
        try:
            return int(val)
        except ValueError:
            return 0

    def get_url_timeout(self) -> int:
        val = self.get("url_timeout", "30000")
        try:
            return int(val)
        except ValueError:
            return 30000

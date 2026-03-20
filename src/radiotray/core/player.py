import logging
from typing import TYPE_CHECKING

from gi.repository import Gst, GLib

from radiotray.models.context import PlaybackState
from radiotray.models.url_info import UrlInfo
from radiotray.decoders import (
    PlsDecoder,
    M3uDecoder,
    AsxDecoder,
    XspfDecoder,
    AsfDecoder,
    RamDecoder,
)
from radiotray.constants import get_default_http_headers
import requests

if TYPE_CHECKING:
    from radiotray.core.mediator import StateMediator
    from radiotray.config.settings import SettingsManager
    from radiotray.events.manager import EventManager


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


class GStreamerPlayer:
    def __init__(
        self,
        mediator: "StateMediator",
        settings: "SettingsManager",
        event_manager: "EventManager",
    ) -> None:
        self.mediator = mediator
        self.settings = settings
        self.event_manager = event_manager
        self.logger = logging.getLogger(__name__)
        self.stream_decoder = StreamDecoder(settings)
        self.playlist: list[str] = []
        self.retrying = False

        self.logger.debug("Initializing GStreamer...")
        self.player = Gst.ElementFactory.make("playbin", "player")
        if self.player is None:
            raise RuntimeError("Failed to create GStreamer playbin element")

        fakesink = Gst.ElementFactory.make("fakesink", "fakesink")
        self.player.set_property("video-sink", fakesink)

        buffer_size = settings.get_buffer_size()
        if buffer_size > 0:
            self.player.set_property("buffer-size", buffer_size)

        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_message)

        self.logger.debug("GStreamer initialized")

    def start(self, url: str) -> None:
        self.logger.info(f"Starting stream: {url}")
        self.playlist = [url]
        self._play_next()

    def _play_next(self) -> None:
        if not self.playlist:
            self.stop()
            self.event_manager.notify(self.event_manager.STATE_CHANGED, {"state": "stopped"})
            return

        stream = self.playlist.pop(0)
        self.logger.info(f"Playing: {stream}")
        self._play_stream(stream)

    def _play_stream(self, uri: str) -> None:
        self.player.set_property("uri", uri)
        self.player.set_state(Gst.State.PLAYING)

    def stop(self) -> None:
        self.logger.info("Stopping GStreamer playback")
        self.player.set_state(Gst.State.NULL)
        self.event_manager.notify(self.event_manager.STATE_CHANGED, {"state": "stopped"})
        self.logger.info("GStreamer stopped")

    def set_volume(self, volume: float) -> None:
        clamped = max(0.0, min(1.0, volume))
        if Gst.ElementFactory.find("playbin"):
            self.player.set_property("volume", clamped)
        self.mediator.update_volume(clamped)

    def volume_up(self) -> None:
        inc = self.settings.get_volume_increment()
        current = self.mediator.context.volume
        self.set_volume(current + inc)

    def volume_down(self) -> None:
        inc = self.settings.get_volume_increment()
        current = self.mediator.context.volume
        self.set_volume(current - inc)

    def _on_message(self, _bus, message) -> bool:
        msg_type = message.type

        if msg_type == Gst.MessageType.EOS:
            self.logger.debug("End of stream")
            self.player.set_state(Gst.State.NULL)
            self._play_next()

        elif msg_type == Gst.MessageType.BUFFERING:
            percent = message.parse_buffering()
            if percent < 100:
                self.player.set_state(Gst.State.PAUSED)
            else:
                self.player.set_state(Gst.State.PLAYING)

        elif msg_type == Gst.MessageType.ERROR:
            self.logger.error(f"GStreamer error: {message.parse_error()}")
            self.player.set_state(Gst.State.NULL)
            if self.playlist:
                self._play_next()
            else:
                self.event_manager.notify(
                    self.event_manager.STATION_ERROR, {"error": message.parse_error()[0].message}
                )

        elif msg_type == Gst.MessageType.STATE_CHANGED:
            old_state, new_state, _ = message.parse_state_changed()
            self.logger.debug(f"State changed: {old_state} -> {new_state}")

            if new_state == Gst.State.PLAYING:
                self.retrying = False
                station = self.mediator.context.station
                self.event_manager.notify(
                    self.event_manager.STATE_CHANGED, {"state": "playing", "station": station}
                )
            elif old_state == Gst.State.PLAYING and new_state == Gst.State.PAUSED:
                if not self.retrying:
                    self.retrying = True
                    GLib.timeout_add(20000, self._check_timeout, None)
                    self.event_manager.notify(self.event_manager.STATE_CHANGED, {"state": "paused"})

        elif msg_type == Gst.MessageType.TAG:
            tag_list = message.parse_tag()

            title = ""
            artist = ""
            album = ""

            _, title = tag_list.get_string("title")
            _, artist = tag_list.get_string("artist")
            _, album = tag_list.get_string("album")

            if not title:
                _, title = tag_list.get_string("song-title")
            if not artist:
                _, artist = tag_list.get_string("album-artist")
            if not artist:
                _, artist = tag_list.get_string("xesam:artist")

            self.logger.info(f"TAG received - title: {title}, artist: {artist}, album: {album}")

            if title or artist:
                self.mediator.context.title = title
                self.mediator.context.artist = artist
                self.mediator.context.album = album

                metadata = {
                    "title": title,
                    "artist": artist,
                    "album": album,
                    "station": self.mediator.context.station,
                }
                self.logger.info(f"Sending SONG_CHANGED: {metadata}")
                self.event_manager.notify(self.event_manager.SONG_CHANGED, metadata)

        elif msg_type == Gst.MessageType.ELEMENT:
            structure = message.get_structure()
            if structure and structure.get_name() == "redirect":
                self.player.set_state(Gst.State.NULL)
                new_location = structure.get_string("new-location")
                if new_location:
                    self.start(new_location)

        return True

    def _check_timeout(self, _data) -> bool:
        if self.retrying:
            self.logger.info("Timeout, retrying...")
            uri = self.player.get_property("uri")
            self._play_stream(uri)
        return False

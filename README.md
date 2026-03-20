# RadioTray [reborn]

A modern online radio streaming player for the Linux system tray, rewritten for Python 3.10+.

## Features

- System tray integration via GTK StatusIcon
- Stream playback using GStreamer
- Plugin system for extensibility
- Desktop notifications
- Song metadata display
- Custom station icons
- Volume control with mouse scroll

## Default Plugins

- **Editor** - Bookmarks Editor for managing stations and groups
- **History** - Shows recently played stations with track info
- **AutoPlay** - Automatically resumes last played station
- **Notification** - Desktop notifications on song change

## Requirements

### Python Dependencies
- Python 3.10+
- PyGObject (GTK 3 bindings)
- lxml
- requests
- pyxdg

### System Dependencies
- GTK 3
- GStreamer 1.0
- libnotify

Install on Debian/Ubuntu/Devuan:
```bash
sudo apt install python3-gi python3-gst-1.0 gir1.2-notify-0.7 \
                 gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
                 gstreamer1.0-plugins-ugly
```

## Installation

```bash
pip install radiotray-reborn
```

Or from source:
```bash
git clone https://github.com/radiotray/radiotray
cd radiotray
pip install .
```

## Usage

Run from command line:
```bash
radiotray
```

## Configuration

Configuration files are stored in:
- Bookmarks: `~/.local/share/radiotray/bookmarks.xml`
- Settings: `~/.local/share/radiotray/config.xml`
- Icons: `~/.local/share/radiotray/icons/`

## Author

**spacedream** - plasma4peace@gmail.com

## License

GPL-3.0-or-later

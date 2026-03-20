#!/usr/bin/env python3

import gi
import sys

gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
gi.require_version("Notify", "0.7")

from radiotray.app import RadioTrayApp, check_single_instance


def main() -> int:
    if not check_single_instance():
        sys.stderr.flush()
        sys.exit(1)

    if len(sys.argv) > 1:
        url = sys.argv[1]
        if url == "--resume":
            url = None
            resume = True
        else:
            resume = False
    else:
        url = None
        resume = False

    app = RadioTrayApp(url=url, resume=resume)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())

"""System tray app: click the icon to toggle monitor mode.

The toggle runs in a worker thread because DDC writes and wake delays
block for several seconds; the tray UI must stay responsive.
"""

from __future__ import annotations

import logging
import threading

import pystray
from PIL import Image, ImageDraw

from . import config, toggle

log = logging.getLogger(__name__)

COLOR_EXTENDED = (70, 160, 90)    # green
COLOR_SINGLE = (200, 130, 40)     # orange
COLOR_UNKNOWN = (150, 150, 150)   # grey


def _make_icon(color: tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGB", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 60, 60), fill=color)
    # two bars representing monitors
    draw.rectangle((16, 22, 30, 42), fill=(20, 20, 20))
    draw.rectangle((34, 22, 48, 42), fill=(20, 20, 20))
    return img


class TrayApp:
    def __init__(self) -> None:
        self._busy = threading.Lock()
        self._icons = {
            config.MODE_EXTENDED: _make_icon(COLOR_EXTENDED),
            config.MODE_SINGLE: _make_icon(COLOR_SINGLE),
            config.MODE_UNKNOWN: _make_icon(COLOR_UNKNOWN),
        }
        self.icon = pystray.Icon(
            "monitor-toggle",
            icon=self._icons[config.get_mode()] if config.get_mode() in self._icons
            else self._icons[config.MODE_UNKNOWN],
            title="Monitor Toggle",
            menu=pystray.Menu(
                pystray.MenuItem("Toggle", self._on_toggle, default=True),
                pystray.MenuItem(self._status_text, None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self._on_quit),
            ),
        )

    @staticmethod
    def _status_text(item) -> str:  # noqa: ARG004 - pystray callback signature
        return f"Mode: {config.get_mode()}"

    def _refresh(self) -> None:
        mode = config.get_mode()
        self.icon.icon = self._icons.get(mode, self._icons[config.MODE_UNKNOWN])
        self.icon.title = f"Monitor Toggle — {mode}"
        self.icon.update_menu()

    def _on_toggle(self, icon=None, item=None) -> None:  # noqa: ARG002
        if not self._busy.acquire(blocking=False):
            log.info("toggle already in progress, ignoring click")
            return
        threading.Thread(target=self._toggle_worker, daemon=True).start()

    def _toggle_worker(self) -> None:
        try:
            new_mode = toggle.toggle()
            self.icon.notify(f"Switched to {new_mode} mode", "Monitor Toggle")
        except Exception as exc:  # noqa: BLE001 - surface any failure to user
            log.exception("toggle failed")
            self.icon.notify(str(exc), "Monitor Toggle — error")
        finally:
            self._refresh()
            self._busy.release()

    def _on_quit(self, icon=None, item=None) -> None:  # noqa: ARG002
        self.icon.stop()

    def run(self) -> None:
        toggle.sync_state()
        self._refresh()
        self.icon.run()


def main() -> None:
    config.APP_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(
                config.APP_DIR / "log.txt", encoding="utf-8"
            ),
            logging.StreamHandler(),
        ],
    )
    TrayApp().run()


if __name__ == "__main__":
    main()

"""Load/save configuration and toggle state.

Config lives in %APPDATA%/monitor-toggle/config.json and is created by
discover.py. State (current mode) lives in state.json next to it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path

APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "monitor-toggle"
CONFIG_PATH = APP_DIR / "config.json"
STATE_PATH = APP_DIR / "state.json"

MODE_EXTENDED = "extended"
MODE_SINGLE = "single"
MODE_UNKNOWN = "unknown"


@dataclass
class Config:
    monitor_index: int          # index into monitorcontrol.get_monitors()
    monitor_name: str           # sanity-check name, informational only
    hdmi_input: int             # VCP 0x60 value for the HDMI input
    pc_input: int               # VCP 0x60 value for the normal PC input
    wake_delay: float = 3.0     # seconds to wait for monitor wake before /extend

    @classmethod
    def load(cls) -> "Config":
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"No config found at {CONFIG_PATH}. Run discover.py first."
            )
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return cls(**data)

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(asdict(self), indent=2), encoding="utf-8"
        )


def get_mode() -> str:
    if not STATE_PATH.exists():
        return MODE_EXTENDED  # assume a normal extended setup initially
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))["mode"]
    except (json.JSONDecodeError, KeyError):
        return MODE_UNKNOWN


def set_mode(mode: str) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"mode": mode}), encoding="utf-8")

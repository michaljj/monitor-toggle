"""Windows display mode switching via the built-in DisplaySwitch.exe."""

from __future__ import annotations

import logging
import subprocess

log = logging.getLogger(__name__)

DISPLAY_SWITCH = "DisplaySwitch.exe"


class DisplayModeError(Exception):
    """Raised when DisplaySwitch.exe fails."""


def _run(arg: str) -> None:
    # DisplaySwitch.exe returns immediately and applies the mode
    # asynchronously; a zero exit code only means the request was accepted.
    result = subprocess.run(
        [DISPLAY_SWITCH, arg],
        capture_output=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise DisplayModeError(
            f"DisplaySwitch.exe {arg} exited with {result.returncode}: "
            f"{result.stderr.decode(errors='replace').strip()}"
        )
    log.info("DisplaySwitch.exe %s accepted", arg)


def set_internal() -> None:
    """PC screen only (first monitor)."""
    _run("/internal")


def set_extend() -> None:
    """Extend displays."""
    _run("/extend")

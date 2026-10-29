"""Toggle orchestration: switch between extended and single+HDMI modes.

Ordering matters:
- to_single(): switch monitor 2's input to HDMI FIRST, while it is still
  enumerated by Windows — after DisplaySwitch /internal the monitor
  disappears from DDC enumeration and its index becomes invalid.
- to_extended(): DisplaySwitch /extend FIRST so monitor 2 is enumerated
  again (in single-display mode its DDC index doesn't exist), wait for
  re-detection, then restore the PC input. The monitor may briefly show
  the HDMI source on the extended desktop before the input switches back.
"""

from __future__ import annotations

import logging
import time

from . import config, ddc, display_mode

log = logging.getLogger(__name__)


class ToggleError(Exception):
    """Raised when a toggle sequence fails partway through."""


def to_single(cfg: config.Config) -> None:
    """Extended -> PC screen only + monitor 2 on HDMI."""
    # DDC first: after /internal the second monitor is no longer enumerated.
    ddc.set_input_source(cfg.monitor_index, cfg.hdmi_input, verify=False)
    try:
        display_mode.set_internal()
    except display_mode.DisplayModeError as exc:
        config.set_mode(config.MODE_UNKNOWN)
        raise ToggleError(
            f"HDMI input switched, but display mode switch failed: {exc}"
        ) from exc
    config.set_mode(config.MODE_SINGLE)
    log.info("now in single-display + HDMI mode")


def to_extended(cfg: config.Config) -> None:
    """Single + HDMI -> extend, wait for re-detection, restore PC input."""
    # /extend first: in single-display mode monitor 2 is not enumerated,
    # so its DDC index is invalid until Windows re-attaches it.
    display_mode.set_extend()
    log.info("waiting %.1fs for monitor re-detection", cfg.wake_delay)
    time.sleep(cfg.wake_delay)
    try:
        ddc.set_input_source(cfg.monitor_index, cfg.pc_input, verify=False)
    except ddc.DDCError as exc:
        config.set_mode(config.MODE_UNKNOWN)
        raise ToggleError(
            f"displays extended, but restoring PC input failed: {exc}"
        ) from exc
    config.set_mode(config.MODE_EXTENDED)
    log.info("now in extended mode")


def sync_state() -> str:
    """Detect the actual current mode from hardware and persist it.

    Called on startup so the tray icon reflects reality even if the state
    file is stale (crash, manual DisplaySwitch use, monitor OSD changes).
    Detection: read monitor 2's input source over DDC — HDMI means single
    mode, the PC input means extended. Falls back to monitor count when
    the input can't be read, then to the persisted state.
    """
    try:
        cfg = config.Config.load()
    except FileNotFoundError:
        return config.get_mode()

    try:
        current = ddc.get_input_source(cfg.monitor_index)
        if current == cfg.hdmi_input:
            mode = config.MODE_SINGLE
        elif current == cfg.pc_input:
            mode = config.MODE_EXTENDED
        else:
            mode = config.MODE_UNKNOWN
    except ddc.DDCError as exc:
        # Monitor 2 not enumerated or unreadable — likely single mode.
        log.info("cannot read monitor %d input (%s); assuming single mode",
                 cfg.monitor_index, exc)
        mode = config.MODE_SINGLE

    config.set_mode(mode)
    log.info("state synced from hardware: %s", mode)
    return mode


def toggle() -> str:
    """Perform the toggle based on persisted state. Returns the new mode."""
    cfg = config.Config.load()
    mode = config.get_mode()
    if mode == config.MODE_EXTENDED:
        to_single(cfg)
    else:
        # MODE_SINGLE or MODE_UNKNOWN: try to get back to extended.
        to_extended(cfg)
    return config.get_mode()

"""DDC/CI input-source control via the monitorcontrol package.

DDC is flaky in practice: writes can silently fail, monitors may be slow
to respond, and reads can raise I/O errors. All operations here retry a
few times and optionally verify by reading the value back.
"""

from __future__ import annotations

import logging
import time

import monitorcontrol

log = logging.getLogger(__name__)

RETRIES = 3
RETRY_DELAY = 0.4  # seconds


class DDCError(Exception):
    """Raised when a DDC operation fails after all retries."""


def list_monitors() -> list[dict]:
    """Enumerate monitors with index, name and current input source."""
    result = []
    for i, mon in enumerate(monitorcontrol.get_monitors()):
        info: dict = {"index": i, "name": "<unknown>", "input": None}
        with mon:
            try:
                caps = mon.get_vcp_capabilities()
                info["name"] = caps.get("model", "<unknown>")
            except Exception as exc:  # noqa: BLE001 - capabilities are optional
                log.debug("monitor %d: could not read capabilities: %s", i, exc)
            try:
                info["input"] = mon.get_input_source()
            except Exception as exc:  # noqa: BLE001
                log.debug("monitor %d: could not read input source: %s", i, exc)
        result.append(info)
    return result


def get_input_source(monitor_index: int) -> int:
    """Read the current input source (VCP 0x60) of a monitor."""
    monitors = monitorcontrol.get_monitors()
    if monitor_index >= len(monitors):
        raise DDCError(
            f"monitor index {monitor_index} out of range "
            f"({len(monitors)} monitor(s) detected)"
        )
    mon = monitors[monitor_index]
    with mon:
        return mon.get_input_source()


def set_input_source(
    monitor_index: int,
    value: int,
    verify: bool = True,
    retries: int = RETRIES,
) -> None:
    """Set the input source (VCP 0x60) of a monitor, with retries.

    Raises DDCError if the write (and optional read-back verification)
    fails after all attempts.
    """
    monitors = monitorcontrol.get_monitors()
    if monitor_index >= len(monitors):
        raise DDCError(
            f"monitor index {monitor_index} out of range "
            f"({len(monitors)} monitor(s) detected)"
        )
    mon = monitors[monitor_index]

    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with mon:
                mon.set_input_source(value)
                if verify:
                    time.sleep(RETRY_DELAY)
                    current = mon.get_input_source()
                    if current != value:
                        raise DDCError(
                            f"read-back mismatch: expected {value:#04x}, "
                            f"got {current:#04x}"
                        )
            log.info("monitor %d: input set to %#04x", monitor_index, value)
            return
        except Exception as exc:  # noqa: BLE001 - retry any DDC failure
            last_exc = exc
            log.warning(
                "monitor %d: set input attempt %d/%d failed: %s",
                monitor_index, attempt, retries, exc,
            )
            time.sleep(RETRY_DELAY)

    raise DDCError(
        f"failed to set input source on monitor {monitor_index} "
        f"after {retries} attempts: {last_exc}"
    )

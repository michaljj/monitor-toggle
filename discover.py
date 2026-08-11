"""One-time hardware discovery tool.

Run this manually before using the tray app:

    python discover.py

It will:
1. Enumerate monitors visible over DDC/CI and show their current input.
2. Let you pick the second monitor.
3. Interactively test candidate VCP 0x60 values until you find HDMI.
4. Record the current (PC) input value.
5. Write config.json for the tray app.

Common VCP 0x60 values (monitor-specific!):
    0x01 VGA, 0x03 DVI-1, 0x0F DisplayPort-1, 0x10 DisplayPort-2,
    0x11 HDMI-1, 0x12 HDMI-2
"""

from __future__ import annotations

import sys

from monitor_toggle import config, ddc

CANDIDATES = [0x11, 0x12, 0x0F, 0x10, 0x03, 0x01]


def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        sys.exit(1)


def main() -> None:
    print("Enumerating monitors...\n")
    monitors = ddc.list_monitors()
    if not monitors:
        print("No monitors with DDC/CI support detected.")
        print("Check that DDC/CI is enabled in the monitor's OSD menu.")
        sys.exit(1)

    for m in monitors:
        current = (
            f"0x{m['input']:02X}" if m["input"] is not None else "unreadable"
        )
        print(f"  [{m['index']}] {m['name']}  current input: {current}")

    answer = _ask("\nIndex of the SECOND monitor (the one to switch to HDMI): ")
    try:
        index = int(answer)
        selected = next(m for m in monitors if m["index"] == index)
    except (ValueError, StopIteration):
        print("Invalid index.")
        sys.exit(1)

    if selected["input"] is None:
        print("Cannot read this monitor's input source — DDC may not work on it.")
        sys.exit(1)

    pc_input = selected["input"]
    print(f"\nCurrent (PC) input recorded as 0x{pc_input:02X}.")
    print("If the PC is NOT connected to the input shown above, fix the")
    print("monitor's input first, then re-run this tool.\n")

    hdmi_input: int | None = None
    print("Testing candidate VCP values. Watch the monitor and confirm")
    print("when it switches to HDMI. (The screen may go black — that's")
    print("expected; answer 'n' to restore the PC input.)\n")
    for value in CANDIDATES:
        answer = _ask(f"Try 0x{value:02X}? [y/n/done] ")
        if answer in ("done", "d"):
            break
        if answer != "y":
            continue
        try:
            ddc.set_input_source(index, value, verify=False)
        except ddc.DDCError as exc:
            print(f"  write failed: {exc}")
            continue
        answer = _ask("Did the monitor switch to HDMI? [y/n] ")
        if answer == "y":
            hdmi_input = value
            break
        # restore PC input before trying the next candidate
        try:
            ddc.set_input_source(index, pc_input, verify=False)
        except ddc.DDCError as exc:
            print(f"  warning: could not restore PC input: {exc}")

    if hdmi_input is None:
        print("\nNo HDMI value found. The monitor may not support DDC input")
        print("switching, or it uses a non-standard value. Check the")
        print("manufacturer's docs and re-run with a custom candidate list.")
        sys.exit(1)

    cfg = config.Config(
        monitor_index=index,
        monitor_name=selected["name"],
        hdmi_input=hdmi_input,
        pc_input=pc_input,
    )
    cfg.save()
    print(f"\nSaved to {config.CONFIG_PATH}:")
    print(f"  monitor: [{index}] {selected['name']}")
    print(f"  HDMI input: 0x{hdmi_input:02X}")
    print(f"  PC input:   0x{pc_input:02X}")
    print("\nYou can now run:  python -m monitor_toggle.tray")


if __name__ == "__main__":
    main()

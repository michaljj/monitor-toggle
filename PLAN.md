# Monitor Toggle Utility — Implementation Plan

## Goal

A small Windows utility that, on a single click (tray icon / taskbar), does the following toggle:

**Mode A → Mode B (extended → single + HDMI):**
1. Switch Windows display mode from "Extend" to "PC screen only" (1st monitor).
2. Switch the second monitor's input source to HDMI (via DDC/CI).

**Mode B → Mode A (single + HDMI → extended):**
1. Switch the second monitor's input source back to its previous input (e.g. DisplayPort).
2. Wait for the monitor to wake / be re-detected.
3. Switch Windows display mode back to "Extend".

State persists between runs so the toggle always knows the current mode.

---

## Feasibility & Key Technical Notes

### Input switching via DDC/CI (`monitorcontrol`)

- Uses VCP code `0x60` (Input Source Select) over the monitor's DDC/CI channel.
- **Not all monitors support DDC input switching** — must be verified on the target hardware first (see Step 1).
- VCP values for inputs are **monitor-specific**. Common values:
  - `0x01` — VGA
  - `0x03` — DVI-1
  - `0x0F` — DisplayPort-1
  - `0x10` — DisplayPort-2
  - `0x11` — HDMI-1
  - `0x12` — HDMI-2
  - Actual values vary by manufacturer/model — discovery is mandatory.
- DDC/CI is flaky: writes can silently fail. All DDC operations need retries (2–3 attempts with ~200–500 ms delay) and read-back verification where possible.

### Windows display mode switching

- Primary approach: built-in `DisplaySwitch.exe`:
  - `DisplaySwitch.exe /internal` — PC screen only
  - `DisplaySwitch.exe /extend` — extend displays
  - `DisplaySwitch.exe /clone`, `/external` also exist if ever needed.
- No admin rights required, no third-party dependencies.
- Alternative (fallback / more control): Win32 `ChangeDisplaySettingsEx` via `pywin32` — allows per-monitor enable/disable and positioning, but significantly more code. Only use if `DisplaySwitch.exe` proves insufficient.

### Taskbar / UI approach

A true taskbar toolbar (deskband) is clunky and deprecated. Practical options, in order of preference:

1. **System tray icon** (`pystray`) — recommended. Shows current mode via icon/tooltip, left-click or menu item toggles, menu also has Quit and status.
2. **Pinned shortcut** to the script — each click toggles, no persistent UI. Simplest possible, but no state feedback.
3. **Global hotkey** (`keyboard` package) — optional bonus alongside the tray icon.

### Ordering & timing caveats

- When switching **to single-display**: run `DisplaySwitch /internal` **before** changing the monitor input, so Windows has already detached the desktop from monitor 2 (avoids stranded windows).
- When switching **back to extended**: restore the monitor input **first**, wait ~2–5 s for the monitor to wake and for Windows to re-detect it, **then** run `DisplaySwitch /extend`. Without the delay, Windows may not see the monitor and the extend may fail or do nothing.
- When the input is switched away, Windows may treat the monitor as disconnected and move windows to monitor 1 on its own — behavior varies by GPU/driver. Must be tested on the actual hardware.

---

## Project Structure

```
monitorControl/
├── pyproject.toml            # deps: monitorcontrol, pystray, pillow
├── monitor_toggle/
│   ├── __init__.py
│   ├── config.py             # load/save config.json (monitor index/id, HDMI VCP value, previous input)
│   ├── ddc.py                # monitorcontrol wrapper: get/set input source with retries
│   ├── display_mode.py       # DisplaySwitch.exe wrapper (/internal, /extend)
│   ├── toggle.py             # state machine + orchestration of the two operations
│   └── tray.py               # pystray tray icon: toggle on click, status, quit
├── discover.py               # one-time CLI: enumerate monitors, read inputs, test VCP values
├── README.md
└── PLAN.md                   # this file
```

### Module responsibilities

**`config.py`**
- Loads/saves `config.json` next to the script (or in `%APPDATA%/monitor-toggle`).
- Contents: monitor identifier (index + name for sanity check), HDMI VCP value, previous/PC input VCP value.
- Also manages `state.json` (current mode: `"extended"` | `"single"`) — or keep state in `toggle.py`; decide during implementation.

**`ddc.py`**
- `get_monitors()` — enumerate via `monitorcontrol`.
- `get_input_source(monitor)` — read VCP `0x60`.
- `set_input_source(monitor, value)` — write VCP `0x60` with retry loop and optional read-back verification.
- Handle `monitorcontrol` exceptions gracefully (monitor asleep, DDC unsupported, I/O errors).

**`display_mode.py`**
- `set_internal()` / `set_extend()` — `subprocess.run(["DisplaySwitch.exe", "/internal"|"/extend"])`, check return code, log result.

**`toggle.py`**
- Reads current state from `state.json`.
- `to_single()`: `set_internal()` → `ddc.set_input_source(HDMI)` → save state.
- `to_extended()`: `ddc.set_input_source(previous_input)` → sleep 2–5 s → `set_extend()` → save state.
- Error handling: if any step fails, log and leave state unchanged (or mark `"unknown"` and offer recovery in tray menu).

**`tray.py`**
- `pystray` icon; icon image/tooltip reflects current mode (generate two simple icons with Pillow, or reuse one with different tooltips).
- Left-click / "Toggle" menu item runs the toggle in a **worker thread** (DDC + sleeps block for seconds — never block the UI thread).
- Menu: Toggle, Current status (disabled item), Quit.

**`discover.py`** (run manually, once)
- List all detected monitors with index and name.
- Read and print current input source (VCP `0x60`) per monitor.
- Optional interactive mode: prompt to try candidate VCP values one by one until HDMI is found; save the result to `config.json`.

---

## Implementation Steps

1. **Project scaffolding**
   - `pyproject.toml` with dependencies: `monitorcontrol`, `pystray`, `pillow`.
   - Package layout as above.

2. **Discovery tool (`discover.py`)** — *do this first, verify hardware*
   - Enumerate monitors, read current VCP `0x60` values.
   - Confirm the second monitor accepts input-source writes and find the HDMI value.
   - Record the "PC" input value (whatever the PC connection uses, e.g. DisplayPort `0x0F`).
   - Write results to `config.json`.

3. **DDC module (`ddc.py`)**
   - Get/set input source with retries and read-back verification.

4. **Display mode module (`display_mode.py`)**
   - Thin wrapper around `DisplaySwitch.exe`.

5. **Toggle logic (`toggle.py`)**
   - State machine as described above, with correct ordering and delays.
   - Test from CLI before building any UI.

6. **Tray app (`tray.py`)**
   - pystray icon, threaded toggle, status display, quit.

7. **Optional extras**
   - Global hotkey (`keyboard` package).
   - Autostart: registry Run key or a shortcut in the Startup folder.
   - File logging (`%APPDATA%/monitor-toggle/log.txt`) for debugging DDC failures.

---

## Risks / Hardware Verification Checklist

| # | Question | How to verify |
|---|----------|---------------|
| 1 | Does monitor 2 respond to VCP `0x60` writes? | `discover.py` — set a value, observe input change |
| 2 | Which VCP value is HDMI on this model? | `discover.py` interactive scan |
| 3 | Does Windows re-detect the monitor reliably after input is restored? | Manual test of `to_extended()` sequence |
| 4 | Does switching input away make Windows move windows / disconnect the display? | Manual test; adjust ordering if needed |
| 5 | Does `DisplaySwitch.exe` behave correctly with this GPU/driver? | Run `/internal` and `/extend` manually |

Only proceed to the tray UI (step 6) after items 1–5 check out.

---

## Dependencies

- Python 3.10+ (Windows)
- [`monitorcontrol`](https://pypi.org/project/monitorcontrol/) — DDC/CI VCP access
- [`pystray`](https://pypi.org/project/pystray/) — system tray icon
- [`pillow`](https://pypi.org/project/Pillow/) — tray icon images (pystray dependency)
- Optional: `keyboard` — global hotkey

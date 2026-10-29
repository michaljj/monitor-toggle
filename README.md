# Monitor Toggle

One-click toggle for a second monitor:

- **Click 1** — Windows switches to "PC screen only" and the second monitor
  switches to HDMI input (via DDC/CI).
- **Click 2** — the monitor switches back to the PC input and Windows
  returns to "Extend displays".

See `PLAN.md` for the full design and hardware caveats.

## Setup

```sh
pip install -e .
```

## 1. Discover your hardware (required, once)

```sh
python discover.py
```

This enumerates monitors, verifies DDC/CI input switching works, finds the
VCP value for HDMI on your monitor, and writes the config to
`%APPDATA%/monitor-toggle/config.json`.

> If no monitors are detected, enable DDC/CI in the monitor's OSD menu.

## 2. Run the tray app

```sh
python -m monitor_toggle.tray
```

Left-click the tray icon (or use its "Toggle" menu) to switch modes.
Icon color shows the current mode: green = extended, orange = single+HDMI.

## Optional: autostart

Create a shortcut to `pythonw.exe -m monitor_toggle.tray` in
`shell:startup` so it starts with Windows.

## Troubleshooting

- **Toggle fails on the HDMI step** — the monitor may not support DDC input
  switching; re-run `discover.py` to confirm.
- **Extend doesn't come back** — increase `wake_delay` in
  `%APPDATA%/monitor-toggle/config.json` (default 3 s).
- **Windows moves windows around when input switches** — GPU/driver
  dependent; see `PLAN.md` risks section.

## License

Licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE.md). Free for
personal, academic and other noncommercial use. Commercial use requires a separate
license — get in touch.

# Project guidance

This is a small hobby hack. Keep the implementation simple, direct, and easy to change.

- Prefer small modules and obvious data flow over abstractions or frameworks.
- Keep code and configuration minimal.
- Do not add documentation or explanatory code comments.
- Keep exception handling lean; handle only failures that need a concrete recovery action.
- Avoid speculative features, compatibility layers, and premature generalization.
- Work directly on `master`; do not create feature branches or worktrees for this repository.

## Where to make changes

- `script.py` contains the current layout/session automation: detector reactions, remote button mappings, train speeds, counters, and timing.
- Prefer making temporary changes and experiments for the current session in `script.py`, using the existing `Automation` methods. Move behavior into the rest of the project later when it needs to become a permanent capability.
- `backend/automation.py` provides the automation hooks and operations used by `script.py`.
- `backend/lego_train.py` and `backend/lego_remote.py` handle LEGO BLE connections and commands.
- `backend/devices.py` handles ESP32 device connections over TCP.
- `backend/api.py` serves the HTTP API and events; `index.html` is the UI.
- `backend/__main__.py` loads configuration and starts the backend and `Script`.
- `firmware/` contains ESP32 firmware. `tools/firmware` builds, uploads, and monitors it with `arduino-cli`.
- `HARDWARE.md` contains wiring and board details; consult it for hardware and firmware work.
- `backend.json` contains train addresses, NFC tags, and server settings; `remote.json` contains remote addresses; `firmware.json` contains board, device, and network settings.
- `backend.json` and `firmware.json` are local, ignored configuration. Do not force-add them or expose network credentials.

## Commands

Read `Makefile` at the start of a task to check the available commands. Prefer these commands for routine operations. Whenever Makefile commands are added, removed, renamed, or changed, update this section in the same change.

| Command | Purpose |
| --- | --- |
| `make backend` | Start the Python backend using the existing `.venv`. |
| `make info` | GET `http://localhost:8080/info`; print the current state of trains, remotes, and devices as JSON. |
| `make restart` | POST `http://localhost:8080/restart`; restart the running backend and reload code/configuration. |
| `make shutdown` | POST `http://localhost:8080/shutdown`; send the power-off command to all connected LEGO trains and remotes. |
| `make scan-ble` | Run `tools/scan-ble` with the existing `.venv`; scan for LEGO hubs for 10 seconds. |
| `make compile [device=TYPE]` | Compile ESP32 firmware; use the configured device when omitted. |
| `make install [device=TYPE]` | Compile and upload ESP32 firmware to the configured USB board. |
| `make monitor` | Open the board's serial monitor. |

The Python commands expect dependencies to be installed in `.venv`; do not add environment setup or package installation to routine targets. The HTTP commands require an already running backend. `make shutdown` powers off LEGO devices, leaving the backend running. After a restart, check `make info` for BLE reconnections before sending device commands.

`help` is currently declared as the default goal but has no recipe; use explicit targets.

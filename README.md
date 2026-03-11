# Break Timer — Setup & Run

## Install dependencies (one time only)
```
pip install pystray pillow flask
```

## Run it

Double-click `break_timer.pyw` in Windows Explorer.

## How it works
- Green circle appears in your system tray
- Counts down 20 minutes silently
- Pops up a reminder when time's up — click "Got it" to reset
- If you lock your screen, the timer pauses automatically
- Right-click the tray icon to: Take break now, Pause/Resume, Reset, or Quit

## REST API

The timer listens on port `5050` on all interfaces, so it's accessible from the local machine or other machines on the same network (e.g. a VirtualBox VM).

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | Current state — remaining time, paused, break in progress |
| POST | `/take-break` | Show the break popup now |
| POST | `/reset` | Reset the countdown |
| POST | `/pause` | Pause the timer |
| POST | `/resume` | Resume the timer |

Example:
```
curl http://localhost:5050/status
curl -X POST http://localhost:5050/pause

## typically from a VM-NAT-guest to the HOST-Windows
curl -X POST http://10.0.2.2:5050/pause
```

`/status` response:
```json
{
  "paused": false,
  "break_in_progress": false,
  "remaining_seconds": 843,
  "remaining": "14:03",
  "elapsed_seconds": 957
}
```

## Run on startup (optional)
1. Press Win+R → type `shell:startup` → Enter
2. Create a shortcut to `break_timer.pyw` in that folder
3. It'll start automatically with Windows

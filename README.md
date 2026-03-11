# Break Timer — Setup & Run

## Install dependencies (one time only)
```
pip install pystray pillow
```

## Run it

Double-click `break_timer.pyw` in Windows Explorer.

## How it works
- Green circle appears in your system tray
- Counts down 20 minutes silently
- Pops up a reminder when time's up — click "Got it" to reset
- If you lock your screen, the timer pauses automatically
- Right-click the tray icon to: Take break now, Pause/Resume, Reset, or Quit

## Run on startup (optional)
1. Press Win+R → type `shell:startup` → Enter
2. Create a shortcut to `break_timer.pyw` in that folder
3. It'll start automatically with Windows

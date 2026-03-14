"""
Break Timer - 20 minute work break reminder
- Runs in system tray
- Pauses automatically when screen is locked
- Pops up a reminder when 20 minutes is up
- REST API on http://localhost:5050
"""

import threading
import time
import tkinter as tk
from tkinter import font as tkfont
import ctypes
from ctypes import wintypes
import sys
import logging
import os
from datetime import datetime, timezone
from PIL import Image, ImageDraw
import pystray
from flask import Flask, jsonify

# ── Config ────────────────────────────────────────────────────────────────────
WORK_MINUTES = 20
WORK_SECONDS = WORK_MINUTES * 60
API_PORT = 5050
SLEEP_DETECT_GAP = 10

# ── Logging ───────────────────────────────────────────────────────────────────
_log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "break_timer.log")
logging.basicConfig(
    filename=_log_file,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("break_timer")
logging.getLogger("werkzeug").setLevel(logging.WARNING)

# ── State ─────────────────────────────────────────────────────────────────────
elapsed = 0
paused = False
running = True
break_showing = False
screen_locked = False
screen_locked_at = None   # epoch when screen was locked
last_wake_at = None       # epoch of last sleep/wake detection
icon_ref = [None]    # set once the tray icon is created
overlay_ref = [None] # set once the taskbar overlay is created


# ── Screen lock detection (Windows) ───────────────────────────────────────────
def is_screen_locked():
    """Returns True if the Windows workstation is locked. Updates screen_locked global and logs transitions."""
    global screen_locked, screen_locked_at, elapsed
    user32 = ctypes.windll.User32
    # OpenInputDesktop returns NULL when the screen is locked
    hDesk = user32.OpenInputDesktop(0, False, 0x0100)
    if hDesk:
        user32.CloseDesktop(hDesk)
        locked = False
    else:
        locked = True

    if locked and not screen_locked:
        screen_locked_at = time.time()
        log.info("Screen locked (elapsed=%ds)", elapsed)
    elif not locked and screen_locked:
        lock_duration = time.time() - screen_locked_at
        log.info("Screen unlocked (elapsed=%ds, locked_for=%.0fs)", elapsed, lock_duration)
        if lock_duration >= WORK_SECONDS:
            elapsed = 0
            log.info("Lock duration >= %ds, resetting timer", WORK_SECONDS)
        screen_locked_at = None

    screen_locked = locked
    return locked


# ── Popup window ──────────────────────────────────────────────────────────────
def show_break_popup(icon):
    """Show a full-attention break reminder popup."""
    global break_showing
    break_showing = True
    log.info("Break popup shown")

    popup = tk.Tk()
    popup.title("Break Time!")
    popup.configure(bg="#0f0f0f")
    popup.attributes("-topmost", True)
    popup.attributes("-fullscreen", False)
    popup.resizable(False, False)

    # Center the window
    w, h = 480, 320
    sw = popup.winfo_screenwidth()
    sh = popup.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    popup.geometry(f"{w}x{h}+{x}+{y}")

    # Content
    frame = tk.Frame(popup, bg="#0f0f0f", padx=40, pady=30)
    frame.pack(expand=True, fill="both")

    emoji_label = tk.Label(frame, text="⏰", font=("Segoe UI Emoji", 48),
                           bg="#0f0f0f", fg="#ffffff")
    emoji_label.pack(pady=(10, 0))

    title_label = tk.Label(frame, text="Time for a break!",
                           font=("Segoe UI", 22, "bold"),
                           bg="#0f0f0f", fg="#ffffff")
    title_label.pack(pady=(8, 4))

    sub_label = tk.Label(frame, text="You've been working for 20 minutes.\nStep away, stretch, rest your eyes.",
                         font=("Segoe UI", 12),
                         bg="#0f0f0f", fg="#888888",
                         justify="center")
    sub_label.pack(pady=(0, 10))

    countdown_label = tk.Label(frame, text="Auto-closing in 1:00",
                               font=("Segoe UI", 10),
                               bg="#0f0f0f", fg="#555555")
    countdown_label.pack(pady=(0, 10))

    dismissed = [False]

    def dismiss():
        if dismissed[0]:
            return
        dismissed[0] = True
        popup.destroy()

    popup.protocol("WM_DELETE_WINDOW", dismiss)

    btn = tk.Button(frame, text="  Got it, starting fresh  ",
                    font=("Segoe UI", 11, "bold"),
                    bg="#2ecc71", fg="#0f0f0f",
                    relief="flat", cursor="hand2",
                    padx=16, pady=8,
                    command=dismiss)
    btn.pack()

    # 1-minute auto-close countdown
    remaining = [60]

    def tick():
        remaining[0] -= 1
        mins = remaining[0] // 60
        secs = remaining[0] % 60
        countdown_label.config(text=f"Auto-closing in {mins}:{secs:02d}")
        if remaining[0] <= 0:
            dismiss()
        else:
            popup.after(1000, tick)

    popup.after(1000, tick)
    popup.mainloop()

    # Single place to reset state — covers dismiss, WM_DELETE_WINDOW, and sleep/lock
    break_showing = False
    if dismissed[0]:
        log.info("Break popup dismissed")
    else:
        log.info("Break popup closed unexpectedly (sleep/lock?)")
    reset_timer(icon)


# ── Timer logic ───────────────────────────────────────────────────────────────
def reset_timer(icon=None):
    global elapsed
    elapsed = 0
    if icon:
        update_tray_title(icon)


def update_tray_title(icon):
    remaining = WORK_SECONDS - elapsed
    mins = remaining // 60
    secs = remaining % 60
    icon.title = f"Break Timer — {mins:02d}:{secs:02d} remaining"


def timer_loop(icon):
    global elapsed, paused, running, last_wake_at

    last_tick = time.time()

    while running:
        time.sleep(1)

        now = time.time()
        gap = now - last_tick
        last_tick = now

        if gap > SLEEP_DETECT_GAP:
            last_wake_at = now
            log.info("Sleep/wake detected (gap=%.0fs)", gap)
            if gap >= WORK_SECONDS:
                elapsed = 0
                log.info("Sleep duration >= %ds, resetting timer", WORK_SECONDS)

        update_tray_title(icon)

        if is_screen_locked():
            # Screen is locked — pause silently
            continue

        if paused:
            continue

        if break_showing:
            continue

        elapsed += 1

        if elapsed >= WORK_SECONDS:
            elapsed = 0
            # Show popup in main thread via tkinter
            threading.Thread(target=show_break_popup, args=(icon,), daemon=True).start()


# ── Taskbar overlay ───────────────────────────────────────────────────────────
def get_taskbar_info():
    class APPBARDATA(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hWnd",   wintypes.HWND),
            ("uCallbackMessage", wintypes.UINT),
            ("uEdge",  wintypes.UINT),
            ("rc",     wintypes.RECT),
            ("lParam", wintypes.LPARAM),
        ]
    abd = APPBARDATA()
    abd.cbSize = ctypes.sizeof(APPBARDATA)
    ctypes.windll.shell32.SHAppBarMessage(5, ctypes.byref(abd))
    return {'left': abd.rc.left, 'top': abd.rc.top,
            'right': abd.rc.right, 'bottom': abd.rc.bottom}


def get_systray_position():
    hwnd = ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None)
    if hwnd:
        tray_notify = ctypes.windll.user32.FindWindowExW(hwnd, None, "TrayNotifyWnd", None)
        if tray_notify:
            rect = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(tray_notify, ctypes.byref(rect))
            return {'left': rect.left, 'top': rect.top,
                    'right': rect.right, 'bottom': rect.bottom}
    return None


def run_overlay():
    root = tk.Tk()
    root.title("Break Timer Overlay")
    root.overrideredirect(True)
    root.attributes('-topmost', True)
    root.attributes('-alpha', 0.95)
    root.configure(bg='#1e1e1e')
    overlay_ref[0] = root

    label = tk.Label(root, text="", font=("Segoe UI", 10, "bold"),
                     fg='#00d4ff', bg='#1e1e1e', padx=10, pady=4)
    label.pack()

    def position_window():
        systray = get_systray_position()
        root.update_idletasks()
        w = root.winfo_width()
        h = root.winfo_height()
        if systray:
            x = systray['left'] - w - 5
            y = systray['top'] + (systray['bottom'] - systray['top'] - h) // 2
        else:
            taskbar = get_taskbar_info()
            x = taskbar['right'] - w - 200
            y = taskbar['top'] + (taskbar['bottom'] - taskbar['top'] - h) // 2
        root.geometry(f"+{x}+{y}")

    was_hidden = [False]

    def update():
        if break_showing:
            if not was_hidden[0]:
                root.withdraw()
                was_hidden[0] = True
        else:
            if was_hidden[0]:
                root.deiconify()
                position_window()
                was_hidden[0] = False
            utc = datetime.now(timezone.utc).strftime("%H:%M:%S")
            remaining = max(0, WORK_SECONDS - elapsed)
            mins = remaining // 60
            secs = remaining % 60
            pause_str = " (P)" if paused else ""
            label.config(text=f"{utc} UTC  {mins:02d}:{secs:02d}{pause_str}")
        root.after(1000, update)

    update()
    position_window()
    root.mainloop()
    log.info("Overlay mainloop exited")


# ── Tray icon ─────────────────────────────────────────────────────────────────
def create_icon_image(color="#2ecc71"):
    """Draw a simple circle icon."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 6
    draw.ellipse([margin, margin, size - margin, size - margin],
                 fill=color, outline="#ffffff", width=3)
    return img


def on_pause_resume(icon, item):
    global paused
    paused = not paused
    log.info("Timer %s", "paused" if paused else "resumed")
    icon.icon = create_icon_image("#e67e22" if paused else "#2ecc71")
    icon.title = "Break Timer — Paused" if paused else "Break Timer"


def on_reset(icon, item):
    reset_timer(icon)


def on_take_break(icon, item):
    global elapsed
    elapsed = 0
    threading.Thread(target=show_break_popup, args=(icon,), daemon=True).start()


def on_quit(icon, item):
    global running
    running = False
    icon.stop()


def build_menu():
    return pystray.Menu(
        pystray.MenuItem("Take break now", on_take_break),
        pystray.MenuItem("Pause / Resume", on_pause_resume),
        pystray.MenuItem("Reset Timer", on_reset),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", on_quit),
    )


# ── REST API ──────────────────────────────────────────────────────────────────
api_app = Flask(__name__)


@api_app.route("/status")
def api_status():
    remaining = max(0, WORK_SECONDS - elapsed)
    lock_epoch = int(screen_locked_at) if screen_locked_at else 0
    lock_fmt = time.strftime("%d-%b-%Y %H:%M:%S", time.localtime(screen_locked_at)) if screen_locked_at else "0"
    wake_epoch = int(last_wake_at) if last_wake_at else 0
    wake_fmt = time.strftime("%d-%b-%Y %H:%M:%S", time.localtime(last_wake_at)) if last_wake_at else "0"
    return jsonify({
        "paused": paused,
        "break_in_progress": break_showing,
        "remaining_seconds": remaining,
        "remaining": f"{remaining // 60:02d}:{remaining % 60:02d}",
        "elapsed_seconds": elapsed,
        "last_screen_lock_epoch": lock_epoch,
        "last_screen_lock_time": lock_fmt,
        "last_wake_epoch": wake_epoch,
        "last_wake_time": wake_fmt,
    })


@api_app.route("/take-break", methods=["POST"])
def api_take_break():
    global elapsed
    elapsed = 0
    icon = icon_ref[0]
    threading.Thread(target=show_break_popup, args=(icon,), daemon=True).start()
    return jsonify({"ok": True})


@api_app.route("/reset", methods=["POST"])
def api_reset():
    reset_timer(icon_ref[0])
    return jsonify({"ok": True})


@api_app.route("/pause", methods=["POST"])
def api_pause():
    global paused
    if not paused:
        on_pause_resume(icon_ref[0], None)
    return jsonify({"ok": True, "paused": paused})


@api_app.route("/resume", methods=["POST"])
def api_resume():
    global paused
    if paused:
        on_pause_resume(icon_ref[0], None)
    return jsonify({"ok": True, "paused": paused})


def start_api():
    log.info("REST API starting on 0.0.0.0:%d", API_PORT)
    api_app.run(host="0.0.0.0", port=API_PORT)


# ── Single instance ───────────────────────────────────────────────────────────
def acquire_single_instance_mutex():
    """Returns a mutex handle if this is the only running instance, else None."""
    ERROR_ALREADY_EXISTS = 183
    handle = ctypes.windll.kernel32.CreateMutexW(None, True, "Global\\BreakTimer_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
        return None
    return handle


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    img = create_icon_image("#2ecc71")
    icon = pystray.Icon(
        name="BreakTimer",
        icon=img,
        title=f"Break Timer — {WORK_MINUTES:02d}:00 remaining",
        menu=build_menu(),
    )
    icon_ref[0] = icon

    log.info("Break Timer started")

    # Start timer thread
    threading.Thread(target=timer_loop, args=(icon,), daemon=True).start()

    # Start REST API thread
    threading.Thread(target=start_api, daemon=True).start()

    # Start taskbar overlay thread
    threading.Thread(target=run_overlay, daemon=True).start()

    icon.run()


if __name__ == "__main__":
    _mutex = acquire_single_instance_mutex()
    if _mutex is None:
        log.warning("Another instance is already running — exiting")
        _root = tk.Tk()
        _root.withdraw()
        import tkinter.messagebox as mb
        mb.showwarning("Already Running", "Break Timer is already running.")
        _root.destroy()
    else:
        main()
        ctypes.windll.kernel32.CloseHandle(_mutex)

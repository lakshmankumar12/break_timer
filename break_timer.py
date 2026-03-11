"""
Break Timer - 20 minute work break reminder
- Runs in system tray
- Pauses automatically when screen is locked
- Pops up a reminder when 20 minutes is up
"""

import threading
import time
import tkinter as tk
from tkinter import font as tkfont
import ctypes
from ctypes import wintypes
import sys
from PIL import Image, ImageDraw
import pystray

# ── Config ────────────────────────────────────────────────────────────────────
WORK_MINUTES = 20
WORK_SECONDS = WORK_MINUTES * 60

# ── State ─────────────────────────────────────────────────────────────────────
elapsed = 0
paused = False
running = True
lock_check_interval = 5  # seconds between lock checks


# ── Screen lock detection (Windows) ───────────────────────────────────────────
def is_screen_locked():
    """Returns True if the Windows workstation is locked."""
    user32 = ctypes.windll.User32
    # OpenInputDesktop returns NULL when the screen is locked
    hDesk = user32.OpenInputDesktop(0, False, 0x0100)
    if hDesk:
        user32.CloseDesktop(hDesk)
        return False
    return True


# ── Popup window ──────────────────────────────────────────────────────────────
def show_break_popup(icon):
    """Show a full-attention break reminder popup."""
    popup = tk.Tk()
    popup.title("Break Time!")
    popup.configure(bg="#0f0f0f")
    popup.attributes("-topmost", True)
    popup.attributes("-fullscreen", False)
    popup.resizable(False, False)

    # Center the window
    w, h = 480, 300
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
    sub_label.pack(pady=(0, 20))

    def dismiss():
        popup.destroy()
        reset_timer(icon)

    btn = tk.Button(frame, text="  Got it, starting fresh  ",
                    font=("Segoe UI", 11, "bold"),
                    bg="#2ecc71", fg="#0f0f0f",
                    relief="flat", cursor="hand2",
                    padx=16, pady=8,
                    command=dismiss)
    btn.pack()

    popup.mainloop()


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
    global elapsed, paused, running

    while running:
        time.sleep(1)

        if is_screen_locked():
            # Screen is locked — pause silently
            continue

        if paused:
            continue

        elapsed += 1
        update_tray_title(icon)

        if elapsed >= WORK_SECONDS:
            elapsed = 0
            # Show popup in main thread via tkinter
            threading.Thread(target=show_break_popup, args=(icon,), daemon=True).start()


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
    icon.icon = create_icon_image("#e67e22" if paused else "#2ecc71")
    icon.title = "Break Timer — Paused" if paused else "Break Timer"


def on_reset(icon, item):
    reset_timer(icon)


def on_quit(icon, item):
    global running
    running = False
    icon.stop()


def build_menu():
    return pystray.Menu(
        pystray.MenuItem("Pause / Resume", on_pause_resume),
        pystray.MenuItem("Reset Timer", on_reset),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", on_quit),
    )


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    img = create_icon_image("#2ecc71")
    icon = pystray.Icon(
        name="BreakTimer",
        icon=img,
        title=f"Break Timer — {WORK_MINUTES:02d}:00 remaining",
        menu=build_menu(),
    )

    # Start timer thread
    t = threading.Thread(target=timer_loop, args=(icon,), daemon=True)
    t.start()

    icon.run()


if __name__ == "__main__":
    main()

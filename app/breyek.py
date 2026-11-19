"""
Breyek 2.0 - eye break assistant for Windows (20-20-20 rule). No AI, no machine learning.

  WAITING  timer is full and still; starts on the first input.
  RUNNING  counts down 20 min of real use. Keyboard, mouse, or a moving screen (video) count as use.
           5 min without any of them resets the timer.
  LOCKED   1 min warm dark cover on every monitor, input blocked, big countdown, a tip, sponsors.

Privacy: by default nothing leaves this computer. Users can opt in (Privacy tab) to share
anonymous usage numbers with the developers; switching it off deletes them again.

Run:  py breyek.py            (20 min / 5 min / 1 min)
      py breyek.py --test     (demo: 20 s / 5 s / 10 s)
Emergency exit while locked: Ctrl + Alt + Shift + Q (Ctrl+Alt+Del always works too).
"""

import argparse
import asyncio
import ctypes
import datetime
import json
import math
import os
import random
import sys
import threading
import time
import tkinter as tk
import urllib.parse
import urllib.request
import webbrowser
import uuid
from ctypes import wintypes
from enum import Enum, auto
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageFont, ImageTk

from pynput import keyboard, mouse

try:
    import winreg
except ImportError:          # not on Windows
    winreg = None
try:      # Windows media controls: pause/resume what is playing (browsers, Spotify, players)
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as MediaManager,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus)
except ImportError:
    MediaManager = None
try:
    import screen_activity as sw    # screen movement detection (no data, no AI)
except ImportError:
    sw = None
import pro                          # Breyek Pro: license check, call detection, sounds

VERSION = "3.0.0"
DEMO = "demo" in os.path.basename(sys.executable if getattr(sys, "frozen", False) else sys.argv[0]).lower() \
    or "--test" in sys.argv
APP_NAME = "Breyek-2.0" + ("-Demo" if DEMO else "")
ICON_FILE = "breyek-demo.ico" if DEMO else "breyek.ico"

# Developers' server for shared usage data. Empty = nothing is ever sent anywhere.
TELEMETRY_URL = "https://breyek-api.breyek-api.workers.dev"
# One inbox for bug reports, support and partners; the subject tag tells them apart.
CONTACT_EMAIL = "breyek@protonmail.com"
PRIVACY_URL = "https://breyek-api.breyek-api.workers.dev/privacy"
POLICY_VERSION = 2          # raise when the policy changes: everyone is asked to agree again
# Sponsors shown during the break and on the Sponsors tab: (name, logo file without _light/_dark.png)
SPONSORS = [("Lietuvos inžinerijos kolegija", "sponsor_lik")]

OVERLAY_ALPHA = 0.92
TIP_ROTATE_SECONDS = 12
TICK_MS = 200
SCREEN_EVERY_S = 1.0

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
USAGE_PATH = os.path.join(CONFIG_DIR, "usage.json")
STATS_PATH = os.path.join(CONFIG_DIR, "stats.json")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
DEFAULTS = {"language": "lt", "corner_timer": True, "screen_watch": True, "theme": "system",
            "eye_filter": False, "filter_strength": 20, "share_data": False, "policy": 0,
            "pause_media": True, "keep_stats": True,
            # Breyek Pro
            "preset": "standard", "work_min": 20, "break_min": 1, "idle_min": 5, "smart_pause": True,
            "snooze": True, "filter_auto": False, "filter_from": 20, "filter_to": 7, "exercises": True,
            "sound": "chime", "snooze_day": "", "snooze_used": 0}
THEMES = ("system", "light", "dark", "midnight", "forest", "paper")
PRO_THEMES = {"midnight", "forest", "paper"}
DARK_THEMES = {"dark", "midnight", "forest"}
PRESETS = {"standard": (20, 1, 5), "pomodoro": (25, 5, 5), "deep": (50, 10, 5)}     # work, break, idle (min)
LIMITS = {"work_min": (5, 120), "break_min": (1, 15), "idle_min": (1, 30), "filter_from": (0, 23),
          "filter_to": (0, 23), "snooze_used": (0, 99)}
HOLD_MAX_S, SNOOZE_S, SNOOZES_PER_DAY, WARN_S = 600, 300, 2, 30
EXERCISES = ("ex_dot", "ex_far", "ex_blink", "ex_palm", "ex_neck")         # Pro break, one every 12 s
FILTER_MIN, FILTER_MAX = 0, 100
FILTER_MAX_ALPHA = 0.5
FILTER_COLOR = "#ff8c1a"

# Warm night palette. dark = "evening": plum night + lamp amber. light = "dusk": rose sand + deep amber.
PALETTES = {
    "dark": {"bg": "#1d1822", "panel": "#27202d", "line": "#3a3040", "fg": "#f1e6dc",
             "muted": "#a3959b", "accent": "#f0a35e", "accent_fg": "#1d1822", "track": "#3a2e36",
             "danger": "#ff8f8f"},
    "light": {"bg": "#f3e9e4", "panel": "#fbf6f2", "line": "#dccbc2", "fg": "#2a2026",
              "muted": "#7b6a6f", "accent": "#b8621b", "accent_fg": "#fbf6f2", "track": "#e6d5cb",
              "danger": "#b3261e"},
    # Pro themes
    "midnight": {"bg": "#141a26", "panel": "#1c2433", "line": "#2c3648", "fg": "#e6e9f0",
                 "muted": "#8f9ab0", "accent": "#e8b45a", "accent_fg": "#141a26", "track": "#2a3344",
                 "danger": "#ff8f8f"},
    "forest": {"bg": "#161e19", "panel": "#1f2922", "line": "#2f3b32", "fg": "#e7eee6",
               "muted": "#94a396", "accent": "#a8d48f", "accent_fg": "#161e19", "track": "#2b372e",
               "danger": "#ff8f8f"},
    "paper": {"bg": "#eceee7", "panel": "#f8f9f4", "line": "#d3d8cc", "fg": "#1f2622",
              "muted": "#66705f", "accent": "#3f7a4d", "accent_fg": "#f8f9f4", "track": "#dfe4d8",
              "danger": "#b3261e"},
}
OVERLAY = {"bg": "#15101a", "title": "#b9a7c2", "timer": "#f6ebe1", "tip": "#f0b878", "small": "#8e8093"}
FONT_NUM = "Bahnschrift"        # Windows 10+; Tk falls back to the default font elsewhere
FONT_TXT = "Segoe UI"

# ---------------------------------------------------------------- languages
def load_languages():
    """Every lang/<code>.json = {"name", "strings", "tips"}. Missing texts fall back to English."""
    folder = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "lang")
    names, strings, tips = {}, {}, {}
    for file in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        try:
            with open(os.path.join(folder, file), encoding="utf-8") as f:
                d = json.load(f)
            code = file[:-5]
            names[code], strings[code], tips[code] = d["name"], d["strings"], d["tips"]
        except (OSError, ValueError, KeyError):
            pass
    return dict(sorted(names.items(), key=lambda kv: kv[1].lower())), strings, tips


def system_language():
    """Windows display language (e.g. 'lt-LT' -> 'lt') if we have it, else English."""
    try:
        buf = ctypes.create_unicode_buffer(85)
        ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85)
        code = buf.value.split("-")[0].lower()
        code = {"no": "nb", "nn": "nb"}.get(code, code)
        return code if code in LANG_NAMES else "en"
    except Exception:
        return "en"


LANG_NAMES, STRINGS, TIPS = load_languages()
DEFAULTS["language"] = system_language()


class State(Enum):
    WAITING = auto()
    RUNNING = auto()
    LOCKED = auto()


# ------------------------------------------------------------ config storage
def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update({k: v for k, v in data.items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    if cfg["language"] not in LANG_NAMES:
        cfg["language"] = DEFAULTS["language"]
    if cfg["theme"] not in THEMES:
        cfg["theme"] = DEFAULTS["theme"]
    for key in ("corner_timer", "screen_watch", "eye_filter", "share_data", "pause_media", "keep_stats"):
        cfg[key] = bool(cfg[key])
    cfg["policy"] = cfg["policy"] if isinstance(cfg["policy"], int) else 0
    for key in ("smart_pause", "snooze", "filter_auto", "exercises"):
        cfg[key] = bool(cfg[key])
    for key, (lo, hi) in LIMITS.items():
        try:
            cfg[key] = max(lo, min(hi, int(cfg[key])))
        except (TypeError, ValueError):
            cfg[key] = DEFAULTS[key]
    if cfg["preset"] not in (*PRESETS, "custom"):
        cfg["preset"] = "standard"
    if cfg["sound"] not in pro.SOUNDS:
        cfg["sound"] = DEFAULTS["sound"]
    try:
        cfg["filter_strength"] = max(FILTER_MIN, min(FILTER_MAX, int(cfg["filter_strength"])))
    except (TypeError, ValueError):
        cfg["filter_strength"] = DEFAULTS["filter_strength"]
    return cfg


def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ------------------------------------------------------------ autostart (registry)
def autostart_command():
    if getattr(sys, "frozen", False):                   # packaged .exe
        return f'"{sys.executable}" --minimized'
    py = sys.executable
    pyw = os.path.join(os.path.dirname(py), "pythonw.exe")   # no console window
    if os.path.exists(pyw):
        py = pyw
    return f'"{py}" "{os.path.abspath(__file__)}" --minimized'


def is_autostart_enabled():
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_NAME)
        return True
    except OSError:
        return False


def set_autostart(enabled):
    """Raises OSError / RuntimeError if the registry cannot be changed."""
    if winreg is None:
        raise RuntimeError("Autostart is only supported on Windows")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


# ------------------------------------------------------------ windows helpers
def enable_dpi_awareness():
    """So Tk geometry and monitor rectangles use the same (real) pixels."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def resource_path(name):
    """Path to a bundled file (works from source and from a PyInstaller .exe)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def set_taskbar_identity():
    """Lets Windows show Breyek's own icon in the taskbar instead of Python's."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{APP_NAME}.App")
    except Exception:
        pass


def dpi_scale():
    try:
        return ctypes.windll.user32.GetDpiForSystem() / 96.0
    except Exception:
        return 1.0


def get_monitors(fallback_root):
    """Return [(x, y, w, h), ...] for every connected monitor."""
    monitors = []
    proc_type = ctypes.WINFUNCTYPE(
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.RECT),
        ctypes.c_void_p,
    )

    def callback(hmon, hdc, rect, data):
        r = rect.contents
        monitors.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
        return 1

    try:
        ctypes.windll.user32.EnumDisplayMonitors(None, None, proc_type(callback), 0)
    except Exception:
        pass

    if not monitors:
        monitors = [(0, 0, fallback_root.winfo_screenwidth(), fallback_root.winfo_screenheight())]
    return monitors


def get_work_area(root):
    """Primary monitor area without the taskbar: (left, top, right, bottom)."""
    try:
        rect = wintypes.RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
            return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)]


def cursor_pos():
    try:
        p = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(p))
        return p.x, p.y
    except Exception:
        return None


def mouse_button_down():
    try:
        return any(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000 for vk in (1, 2, 4))
    except Exception:
        return False


def foreground_fullscreen():
    """True when the active window covers its whole monitor (games, full-screen video)."""
    try:
        u = ctypes.windll.user32
        u.GetForegroundWindow.restype = wintypes.HWND
        u.MonitorFromWindow.restype = wintypes.HMONITOR
        u.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        hwnd = u.GetForegroundWindow()
        if not hwnd:
            return False
        cls = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(hwnd, cls, 64)
        if cls.value in ("Progman", "WorkerW", "Shell_TrayWnd"):     # desktop and taskbar
            return False
        r, mi = wintypes.RECT(), MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        u.GetWindowRect(hwnd, ctypes.byref(r))
        u.GetMonitorInfoW(u.MonitorFromWindow(hwnd, 2), ctypes.byref(mi))
        m = mi.rcMonitor
        return r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom
    except Exception:
        return False


def seconds_since_last_input():
    """System-wide idle time: seconds since the last keyboard/mouse input in ANY app.
    Returns None if Windows cannot tell (e.g. not running on Windows)."""
    try:
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        kernel32 = ctypes.windll.kernel32
        kernel32.GetTickCount.restype = wintypes.DWORD
        return ((kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0
    except Exception:
        return None


def system_prefers_dark():
    """True when Windows apps are set to dark mode (Settings > Personalization > Colors)."""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", 0, winreg.KEY_READ,
        ) as key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def set_titlebar(root, dark, bg, fg):
    """Title bar in the theme colours: dark mode (Windows 10 1809+) and exact caption colour (Windows 11)."""
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
        dwm = ctypes.windll.dwmapi.DwmSetWindowAttribute
        put = lambda attr, v: dwm(hwnd, attr, ctypes.byref(ctypes.c_int(v)), 4)
        if put(20, int(dark)) != 0:                     # DWMWA_USE_IMMERSIVE_DARK_MODE (older id: 19)
            put(19, int(dark))
        bgr = lambda h: int(h[5:7] + h[3:5] + h[1:3], 16)
        put(35, bgr(bg))                                 # DWMWA_CAPTION_COLOR
        put(36, bgr(fg))                                 # DWMWA_TEXT_COLOR
        put(34, bgr(bg))                                 # DWMWA_BORDER_COLOR
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x37)    # redraw the frame now
    except Exception:
        pass


def ring_image(d, w, share, track, color, bg):
    """Countdown ring drawn 4x larger and scaled down: smooth edges and round ends."""
    s, D = 4, d * 4
    img = Image.new("RGB", (D, D), bg)
    draw = ImageDraw.Draw(img)
    box, W = (s, s, D - s, D - s), w * s
    draw.ellipse(box, outline=track, width=W)
    if share > 0.002:
        start, end = -90, -90 + 360 * share
        draw.arc(box, start, end, fill=color, width=W)
        r, c = (D - 2 * s - W) / 2, D / 2
        for a in (math.radians(start), math.radians(end)):
            x, y = c + r * math.cos(a), c + r * math.sin(a)
            draw.ellipse((x - W / 2, y - W / 2, x + W / 2, y + W / 2), fill=color)
    return ImageTk.PhotoImage(img.resize((d, d), Image.LANCZOS))

def fmt(seconds):
    seconds = max(0, math.ceil(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


# ---------------------------------------------------------------- eye filter
def filter_alpha(percent):
    return max(0.0, min(1.0, percent / 100.0 * FILTER_MAX_ALPHA))


class EyeFilter:
    """Warm see-through tint over every monitor (less blue light). Clicks pass straight through."""

    def __init__(self, root):
        self.root = root
        self.wins = []
        self.monitors = []
        self.strength = None
        self._next_refresh = 0.0

    def _click_through(self, win):
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
            style = user32.GetWindowLongW(hwnd, -20)
            style |= 0x00080000 | 0x00000020 | 0x00000080 | 0x08000000
            # LAYERED | TRANSPARENT | TOOLWINDOW | NOACTIVATE
            user32.SetWindowLongW(hwnd, -20, style)
        except Exception:
            pass

    def _create(self, monitors):
        self._destroy()
        self.monitors = list(monitors)
        for (x, y, w, h) in self.monitors:
            win = tk.Toplevel(self.root)
            win.overrideredirect(True)
            win.configure(bg=FILTER_COLOR, cursor="arrow")
            win.geometry(f"{w}x{h}+{x}+{y}")
            win.attributes("-topmost", True)
            win.attributes("-alpha", filter_alpha(self.strength or 0))
            win.update_idletasks()
            self._click_through(win)
            self.wins.append(win)

    def _destroy(self):
        for win in self.wins:
            try:
                win.destroy()
            except tk.TclError:
                pass
        self.wins = []
        self.monitors = []

    def update(self, want, strength, now):
        """Call every tick. Creates / removes the tint and keeps it current."""
        if not want:
            if self.wins:
                self._destroy()
            return False
        refreshed = False
        if not self.wins or (now >= self._next_refresh and get_monitors(self.root) != self.monitors):
            self.strength = strength
            self._create(get_monitors(self.root))
            refreshed = True
        if strength != self.strength:
            self.strength = strength
            for win in self.wins:
                try:
                    win.attributes("-alpha", filter_alpha(strength))
                except tk.TclError:
                    pass
        if now >= self._next_refresh:
            self._next_refresh = now + 2.0
            for win in self.wins:        # stay above other always-on-top windows
                try:
                    win.lift()
                    win.attributes("-topmost", True)
                except tk.TclError:
                    pass
            refreshed = True
        return refreshed

    def close(self):
        self._destroy()


# ------------------------------------------------------------ activity statistics (local only)
CATS = ("work", "browse", "game", "watch", "read")
CAT_COLORS = {"work": "#f0a35e", "browse": "#d6b47c", "game": "#e0788c", "watch": "#a596dc", "read": "#78b4a0"}


class ActivityStats:
    """Seconds per activity type per day in stats.json: 60 days (Pro: a year). Only totals are ever shared."""

    def __init__(self, cfg):
        self.cfg, self.days, self._unsaved = cfg, {}, 0.0
        self.keep_days = 60                     # Pro: 365
        try:
            with open(STATS_PATH, "r", encoding="utf-8") as f:
                self.days = json.load(f).get("days", {})
        except (OSError, ValueError, AttributeError):
            pass

    def day(self, date):
        return self.days.get(date.isoformat(), {})

    def add(self, cat, seconds):
        if not self.cfg["keep_stats"]:
            return
        d = self.days.setdefault(datetime.date.today().isoformat(), {})
        d[cat] = d.get(cat, 0) + seconds
        self._unsaved += seconds
        if self._unsaved >= 60:
            self.save()

    def add_break(self):
        if self.cfg["keep_stats"]:
            d = self.days.setdefault(datetime.date.today().isoformat(), {})
            d["breaks"] = d.get("breaks", 0) + 1
            self.save()

    def last(self, n):
        today = datetime.date.today()
        return [(today - datetime.timedelta(days=i), self.day(today - datetime.timedelta(days=i)))
                for i in range(n - 1, -1, -1)]

    def export_csv(self, path):
        import csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["date", *[f"{c}_min" for c in CATS], "breaks"])
            for day in sorted(self.days):
                d = self.days[day]
                w.writerow([day, *[round(d.get(c, 0) / 60) for c in CATS], d.get("breaks", 0)])

    def save(self):
        self._unsaved = 0.0
        oldest = (datetime.date.today() - datetime.timedelta(days=self.keep_days)).isoformat()
        self.days = {k: v for k, v in self.days.items() if k >= oldest}
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(STATS_PATH, "w", encoding="utf-8") as f:
                json.dump({"days": self.days}, f, indent=1)
        except OSError:
            pass

    def delete(self):
        self.days, self._unsaved = {}, 0.0
        try:
            os.remove(STATS_PATH)
        except OSError:
            pass


def fmt_hm(seconds, pattern):
    m = int(seconds // 60)
    return pattern.format(h=m // 60, m=m % 60)


# ------------------------------------------------------------ usage data (opt-in only)
class UsageStats:
    """Counts breaks and minutes of use per day - ONLY while the user has opted in.
    Switching the option off deletes the file. Nothing is sent unless TELEMETRY_URL is set."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.stats = None             # ActivityStats: its per-type totals are shared too (opt-in only)
        self.data = {"install_id": None, "last_sent": None, "days": {}}
        self._pending_s = 0.0
        try:
            with open(USAGE_PATH, "r", encoding="utf-8") as f:
                self.data.update(json.load(f))
        except (OSError, ValueError):
            pass

    @property
    def enabled(self):
        return bool(self.cfg.get("share_data"))

    def _today(self):
        return self.data["days"].setdefault(datetime.date.today().isoformat(), {"breaks": 0, "active_min": 0})

    def _save(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(USAGE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=1)
        except OSError:
            pass

    def add_active(self, seconds):
        if not self.enabled:
            return
        self._pending_s += seconds
        if self._pending_s >= 60:
            self._today()["active_min"] += int(self._pending_s // 60)
            self._pending_s %= 60
            self._save()

    def add_break(self):
        if self.enabled:
            self._today()["breaks"] += 1
            self._save()
            self.maybe_send()

    def today(self):
        return self.data["days"].get(datetime.date.today().isoformat(), {"breaks": 0, "active_min": 0})

    def delete(self):
        """Opt-out: forget everything here and ask the server to delete what it already has."""
        sent_id = self.data.get("install_id") if self.data.get("last_sent") else None
        if sent_id and TELEMETRY_URL:
            threading.Thread(target=self._post, args=({"install_id": sent_id, "delete": True},), daemon=True).start()
        self.data = {"install_id": None, "last_sent": None, "days": {}}
        self._pending_s = 0.0
        try:
            os.remove(USAGE_PATH)
        except OSError:
            pass

    def maybe_send(self):
        """At most once a day, in the background. Never runs while the option is off."""
        today = datetime.date.today().isoformat()
        if not (self.enabled and TELEMETRY_URL) or self.data.get("last_sent") == today:
            return
        if not self.data.get("install_id"):
            self.data["install_id"] = uuid.uuid4().hex      # random, not tied to a person or device
        # only finished days, each sent once, and nothing from before sharing was switched on
        since = self.data.get("last_sent") or self.data.setdefault("opted_in", today)
        days = {d: v for d, v in self.data["days"].items() if d < today}
        activity = {day: {k: int(v // 60) for k, v in vals.items() if k in CATS}      # minutes per type
                    for day, vals in (self.stats.days.items() if self.stats else []) if since <= day < today}
        if not days and not activity:
            return
        payload = {"install_id": self.data["install_id"], "version": VERSION, "demo": DEMO,
                   "language": self.cfg["language"], "theme": self.cfg["theme"], "days": days,
                   "activity": activity}

        def send():
            if self._post(payload):
                self.data["last_sent"] = today
                for d in days:
                    self.data["days"].pop(d, None)
                self._save()           # if offline: try again after the next break

        threading.Thread(target=send, daemon=True).start()

    @staticmethod
    def _post(body):
        try:
            req = urllib.request.Request(TELEMETRY_URL, data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json", "User-Agent": "Breyek"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status == 200
        except Exception:
            return False


# ------------------------------------------------------------------- break cover
def load_image(name, theme):
    """Sponsor logo for a light or dark background (PNG next to the script / inside the exe)."""
    try:
        return tk.PhotoImage(file=resource_path(f"{name}_{'light' if theme in DARK_THEMES else 'dark'}.png"))
    except tk.TclError:
        return None


# Fonts for the break screen, drawn with Pillow so big text stays smooth on a see-through window.
LANG_FONTS = {"zh": ["msyh.ttc", "simsun.ttc"], "ja": ["YuGothM.ttc", "meiryo.ttc", "msgothic.ttc"],
              "ko": ["malgun.ttf"], "ka": ["sylfaen.ttf"]}
_fonts = {}


def find_font(kind, lang):
    folder = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    names = (["bahnschrift.ttf"] if kind == "num" else LANG_FONTS.get(lang, [])) + ["segoeui.ttf", "arial.ttf"]
    return next((os.path.join(folder, n) for n in names if os.path.exists(os.path.join(folder, n))), None)


def text_image(text, kind, lang, px, color, bg, max_w=None):
    """Antialiased, centred, word-wrapped text as a Tk image (None when no font file is found)."""
    path = find_font(kind, lang)
    if not path or not text:
        return None
    try:
        font = _fonts.get((path, px)) or _fonts.setdefault((path, px), ImageFont.truetype(path, px))
    except OSError:
        return None
    width = lambda t: font.getlength(t)
    lines = []
    for word in text.split(" ") if " " in text else list(text):      # no spaces (CJK): wrap by character
        sep = " " if " " in text else ""
        if lines and max_w and width(lines[-1] + sep + word) > max_w:
            lines.append(word)
        else:
            lines[-1:] = [(lines[-1] + sep + word) if lines else word]
    ascent, descent = font.getmetrics()
    line_h, top = int((ascent + descent) * 1.15), 0
    img_w = int(max(width(l) for l in lines)) + 8
    img_h = line_h * len(lines) + 4
    if kind == "num":                                  # big digits: crop to the ink, no empty line space
        x0, y0, x1, y1 = font.getbbox(text, anchor="ma")
        top, img_h = -y0 + 2, y1 - y0 + 4
    img = Image.new("RGB", (img_w, img_h), bg)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((img_w / 2, top + i * line_h), line, font=font, fill=color, anchor="ma")
    return ImageTk.PhotoImage(img)


class Overlay:
    """Warm dark, borderless, always-on-top window covering one monitor."""

    def __init__(self, root, x, y, w, h, title_text, sponsor_text, lang):
        o = self.o = OVERLAY
        self.w, self.h, self.lang, self.shown = w, h, lang, {}
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.configure(bg=o["bg"], cursor="none")
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", OVERLAY_ALPHA)

        box = tk.Frame(self.win, bg=o["bg"])
        box.place(relx=0.5, rely=0.44, anchor="center")
        self.title, self.timer, self.tip = (tk.Label(box, bg=o["bg"]) for _ in range(3))
        self.title.pack(pady=(0, int(h * 0.035)))
        self.timer.pack(pady=(0, int(h * 0.045)))
        self.tip.pack()
        self._set(self.title, title_text, "txt", 0.035, o["title"])
        self.dot_w, self.dot_h = int(w * 0.36), int(h * 0.16)
        self.dot = tk.Canvas(box, width=self.dot_w, height=self.dot_h, bg=o["bg"], highlightthickness=0)
        r = max(6, int(h * 0.012))
        self.dot_item = self.dot.create_oval(0, 0, 2 * r, 2 * r, fill=o["tip"], outline="")
        self.dot_r, self.dot_on, self.dot_t = r, False, 0.0

        self.logos = [img for img in (load_image(f, "dark") for _, f in SPONSORS) if img] if sponsor_text else []
        if self.logos:
            foot = tk.Frame(self.win, bg=o["bg"])
            foot.place(relx=0.5, rely=0.93, anchor="s")
            label = tk.Label(foot, bg=o["bg"])
            label.pack(pady=(0, int(h * 0.008)))
            self._set(label, sponsor_text, "txt", 0.017, o["small"])
            for img in self.logos:
                tk.Label(foot, image=img, bg=o["bg"]).pack(side="left", padx=12)

    def _set(self, label, text, kind, size, color, wrap=None):
        if self.shown.get(id(label)) == text:
            return
        self.shown[id(label)] = text
        px = int(self.h * size)
        img = text_image(text, kind, self.lang, px, color, self.o["bg"], wrap)
        if img is not None:
            label.configure(image=img, text="")
            label.img = img
        else:                                   # no font file: let Tk draw it
            label.configure(image="", text=text, fg=color, font=(FONT_NUM if kind == "num" else FONT_TXT, -px),
                            wraplength=wrap or 0, justify="center")

    def update(self, timer_text, tip_text, dot=False):
        self._set(self.timer, timer_text, "num", 0.24, self.o["timer"])
        self._set(self.tip, tip_text, "txt", 0.03, self.o["tip"], int(self.w * 0.55))
        if dot != self.dot_on:
            self.dot_on = dot
            if dot:
                self.dot.pack(pady=(int(self.h * 0.03), 0))
                self._move_dot()
            else:
                self.dot.pack_forget()

    def _move_dot(self):
        """Slow figure-eight for the eyes to follow."""
        if not self.dot_on:
            return
        self.dot_t += 0.025
        x = (0.5 + 0.45 * math.sin(self.dot_t)) * self.dot_w
        y = (0.5 + 0.38 * math.sin(2 * self.dot_t)) * self.dot_h
        r = self.dot_r
        try:
            self.dot.coords(self.dot_item, x - r, y - r, x + r, y + r)
            self.win.after(33, self._move_dot)
        except tk.TclError:
            pass

    def keep_on_top(self):
        try:
            self.win.lift()
            self.win.attributes("-topmost", True)
        except tk.TclError:
            pass

    def close(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass


class MediaPause:
    """Pauses whatever is playing when the break starts and resumes exactly that afterwards."""

    def __init__(self):
        self.paused = []          # app ids of the media sessions we paused
        self.used_key = False     # fallback: we pressed the Play/Pause media key

    @staticmethod
    def _run(coro):
        return asyncio.run(asyncio.wait_for(coro, timeout=2))

    @staticmethod
    async def _pause_playing():
        manager, paused = await MediaManager.request_async(), []
        for session in manager.get_sessions():
            if session.get_playback_info().playback_status == PlaybackStatus.PLAYING:
                if await session.try_pause_async():
                    paused.append(session.source_app_user_model_id)
        return paused

    @staticmethod
    async def _play(ids):
        manager = await MediaManager.request_async()
        for session in manager.get_sessions():
            if session.source_app_user_model_id in ids:
                await session.try_play_async()

    @staticmethod
    def _media_key():
        try:
            user32 = ctypes.windll.user32
            user32.keybd_event(0xB3, 0, 0, 0)          # VK_MEDIA_PLAY_PAUSE down
            user32.keybd_event(0xB3, 0, 2, 0)          # ... and up
        except Exception:
            pass

    def pause(self, video_likely):
        self.paused, self.used_key = [], False
        if MediaManager is not None:
            try:
                self.paused = self._run(self._pause_playing())
                return
            except Exception:
                pass
        if video_likely:            # no media controls: the Play/Pause key only if a video seems to play
            self._media_key()
            self.used_key = True

    def resume(self):
        try:
            if self.paused:
                self._run(self._play(self.paused))
            elif self.used_key:
                self._media_key()
        except Exception:
            pass
        self.paused, self.used_key = [], False


def click_through(win):
    """Mouse clicks pass through the window to whatever is below it."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
        style = user32.GetWindowLongW(hwnd, -20)                       # GWL_EXSTYLE
        user32.SetWindowLongW(hwnd, -20, style | 0x00080000 | 0x00000020 | 0x00000080 | 0x08000000)
        # LAYERED | TRANSPARENT | TOOLWINDOW | NOACTIVATE
    except Exception:
        pass


class CornerTimer:
    """Small always-on-top timer in the bottom-right corner. Clicks go through it."""

    MARGIN = 12

    def __init__(self, root, scale):
        self.root = root
        self.visible = True
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.9)
        self.label = tk.Label(self.win, text="00:00", font=(FONT_NUM, -int(20 * scale)),
                              padx=int(12 * scale), pady=int(3 * scale))
        self.label.pack()
        self.set_colors(PALETTES["dark"])
        self._place()
        click_through(self.win)
        self.set_visible(False)

    def set_colors(self, c):
        self.c = c
        self.win.configure(bg=c["panel"])
        self.label.configure(bg=c["panel"])

    def _place(self):
        self.win.update_idletasks()
        w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        left, top, right, bottom = get_work_area(self.root)
        self.win.geometry(f"+{right - w - self.MARGIN}+{bottom - h - self.MARGIN}")

    def set_visible(self, visible):
        if visible == self.visible:
            return
        self.visible = visible
        if visible:
            self._place()
            self.win.deiconify()
            click_through(self.win)
            self.win.attributes("-topmost", True)
        else:
            self.win.withdraw()

    def set_text(self, text, active):
        self.label.configure(text=text, fg=self.c["accent"] if active else self.c["muted"])

    def close(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass


# ----------------------------------------------------------------------- app
class BreyekApp:
    RING = 150              # diameter of the countdown ring, px at 96 dpi

    def __init__(self, work_s, idle_s, break_s, start_minimized=False):
        self.base_timing = self.work_s, self.idle_s, self.break_s = work_s, idle_s, break_s
        self.cfg = load_config()
        self.license = pro.ProLicense(CONFIG_DIR)
        self.lang = self.cfg["language"]
        self.usage = UsageStats(self.cfg)

        enable_dpi_awareness()
        set_taskbar_identity()
        self.root = tk.Tk()
        self.scale = dpi_scale()
        try:
            self.root.iconbitmap(resource_path(ICON_FILE))
        except tk.TclError:
            pass
        self.c = PALETTES["dark"]
        self._theme_applied = None
        self._next_theme_check = 0.0
        self.eyefilter = EyeFilter(self.root)

        self.state = State.WAITING
        self.state_since = time.monotonic()
        self.last_input = 0.0
        self.run_start = 0.0
        self.lock_end = 0.0
        self.next_tip_at = 0.0
        self.current_tip = ""
        self.overlays = []
        self.blockers = []
        self.emergency = False
        self._quitting = False
        self._held = set()
        self._last_tick = time.monotonic()
        self.media = MediaPause()
        self.stats = ActivityStats(self.cfg)
        self.usage.stats = self.stats
        self.stats_n = 7                              # days shown in the chart (Pro: 7 or 30)
        self.hold_since = None                        # Pro smart pause: break waiting since
        self._busy, self._next_busy = False, 0.0
        self.toast = None
        self.ex_index, self.current_dot, self._lic_dirty = 0, False, False
        self.last_kb = self.last_mouse = 0.0          # when the keyboard / the mouse was last used
        self._input_at, self._cursor = 0.0, cursor_pos()
        self.fullscreen, self._next_fs, self._next_chart = False, 0.0, 0.0

        self.screen = sw.ScreenWatcher() if sw else None
        self.screen_on = self.screen is not None and self.cfg["screen_watch"]
        self.last_screen = 0.0
        self._next_screen = 0.0

        self._build_window()
        self._apply_pro()
        self.corner = CornerTimer(self.root, self.scale)
        self.apply_theme()
        self.apply_language()
        self.root.after(150, lambda: set_titlebar(self.root, self._theme_applied in DARK_THEMES,
                                                  self.c["bg"], self.c["fg"]))   # once the window exists
        if start_minimized:
            self.root.after(100, self.root.iconify)

    # ------------------------------------------------- UI
    def t(self, key, **kw):
        text = STRINGS.get(self.lang, {}).get(key) or STRINGS["en"][key]
        return text.format(**kw) if kw else text

    def px(self, v):
        return int(v * self.scale)

    def _build_window(self):
        r = self.root
        r.resizable(False, False)
        r.protocol("WM_DELETE_WINDOW", lambda: r.iconify())     # keep running in the background
        W = self.px(380)

        main = ttk.Frame(r, padding=(self.px(20), self.px(16), self.px(20), self.px(14)))
        main.pack(fill="both", expand=True)

        head = ttk.Frame(main)                  # ring on the left, name and status on the right
        head.pack(fill="x", pady=(0, self.px(14)))
        d = self.px(self.RING)
        self.ring = tk.Canvas(head, width=d, height=d, highlightthickness=0, bd=0)
        self.ring.pack(side="left")
        self.ring_w, self.ring_d, self._ring_key = self.px(8), d, None
        self.ring_bg = self.ring.create_image(d / 2, d / 2)
        self.ring_time = self.ring.create_text(d / 2, d / 2, font=(FONT_NUM, -self.px(34)))
        side = ttk.Frame(head)
        side.pack(side="left", fill="both", expand=True, padx=(self.px(18), 0))
        ttk.Label(side, text="Breyek", style="Brand.TLabel").pack(anchor="w", pady=(self.px(18), self.px(6)))
        self.lbl_status = ttk.Label(side, wraplength=W - d - self.px(70), justify="left")
        self.lbl_status.pack(anchor="w")
        self.lbl_screen = ttk.Label(side, style="Muted.TLabel", wraplength=W - d - self.px(70), justify="left")
        self.lbl_screen.pack(anchor="w", pady=(self.px(4), 0))
        if DEMO:
            ttk.Label(side, text=f"demo · {self.work_s}/{self.idle_s}/{self.break_s} s",
                      style="Muted.TLabel").pack(anchor="w", pady=(self.px(4), 0))

        self.tabs = ttk.Notebook(main)
        self.tabs.pack(fill="both", expand=True)
        pad = (self.px(14), self.px(12))
        self.tab_settings = ttk.Frame(self.tabs, padding=pad, style="Panel.TFrame")
        self.tab_privacy = ttk.Frame(self.tabs, padding=pad, style="Panel.TFrame")
        self.tab_sponsors = ttk.Frame(self.tabs, padding=pad, style="Panel.TFrame")
        self.tab_stats = ttk.Frame(self.tabs, padding=pad, style="Panel.TFrame")
        self.tab_pro = ttk.Frame(self.tabs, padding=pad, style="Panel.TFrame")
        for tab in (self.tab_settings, self.tab_stats, self.tab_pro, self.tab_privacy, self.tab_sponsors):
            self.tabs.add(tab)

        # --- settings tab
        s = self.tab_settings
        self.var_autostart = tk.BooleanVar(value=is_autostart_enabled())
        self.chk_autostart = ttk.Checkbutton(s, variable=self.var_autostart, command=self._on_autostart)
        self.chk_autostart.pack(anchor="w")
        if DEMO:
            self.var_autostart.set(False)
            self.chk_autostart.state(["disabled"])          # a 20 s demo must never autostart
        self.var_corner = tk.BooleanVar(value=self.cfg["corner_timer"])
        self.chk_corner = ttk.Checkbutton(s, variable=self.var_corner, command=self._on_corner)
        self.chk_corner.pack(anchor="w", pady=(self.px(6), 0))
        self.var_screen = tk.BooleanVar(value=self.screen_on)
        self.chk_screen = ttk.Checkbutton(s, variable=self.var_screen, command=self._on_screen)
        self.chk_screen.pack(anchor="w", pady=(self.px(6), 0))
        if self.screen is None:
            self.chk_screen.state(["disabled"])
        self.var_media = tk.BooleanVar(value=self.cfg["pause_media"])
        self.chk_media = ttk.Checkbutton(s, variable=self.var_media, command=self._on_media)
        self.chk_media.pack(anchor="w", pady=(self.px(6), 0))
        self.var_filter = tk.BooleanVar(value=self.cfg["eye_filter"])
        self.chk_filter = ttk.Checkbutton(s, variable=self.var_filter, command=self._on_filter)
        self.chk_filter.pack(anchor="w", pady=(self.px(6), 0))
        row = ttk.Frame(s, style="Panel.TFrame")
        row.pack(fill="x", padx=(self.px(26), 0), pady=(self.px(2), 0))
        self.lbl_strength = ttk.Label(row, style="PanelMuted.TLabel")
        self.lbl_strength.pack(side="left")
        self.scale_w = ttk.Scale(row, from_=FILTER_MIN, to=FILTER_MAX, orient="horizontal",
                                 command=self._on_strength)
        self.scale_w.pack(side="left", fill="x", expand=True, padx=(self.px(8), 0))
        self.var_pct = tk.StringVar()                       # typed percent, also arrows / mouse wheel
        self.spin_pct = ttk.Spinbox(row, from_=FILTER_MIN, to=FILTER_MAX, increment=1, width=4,
                                    textvariable=self.var_pct, command=self._on_pct_typed, justify="right")
        self.spin_pct.pack(side="left", padx=(self.px(8), 0))
        ttk.Label(row, text="%", style="Panel.TLabel").pack(side="left", padx=(self.px(2), 0))
        for ev in ("<Return>", "<FocusOut>", "<KP_Enter>"):
            self.spin_pct.bind(ev, self._on_pct_typed)
        self.scale_w.set(self.cfg["filter_strength"])      # after spin_pct: set() calls _on_strength
        self.scale_w.bind("<ButtonRelease-1>", lambda e: save_config(self.cfg))
        self._sync_filter_widgets()

        grid = ttk.Frame(s, style="Panel.TFrame")
        grid.pack(fill="x", pady=(self.px(12), 0))
        grid.columnconfigure(1, weight=1)
        self.lbl_theme = ttk.Label(grid, style="Panel.TLabel")
        self.lbl_theme.grid(row=0, column=0, sticky="w", padx=(0, self.px(10)))
        self.cmb_theme = ttk.Combobox(grid, state="readonly")
        self.cmb_theme.grid(row=0, column=1, sticky="ew")
        self.cmb_theme.bind("<<ComboboxSelected>>", self._on_theme)
        self.lbl_lang = ttk.Label(grid, style="Panel.TLabel")
        self.lbl_lang.grid(row=1, column=0, sticky="w", padx=(0, self.px(10)), pady=(self.px(6), 0))
        self.var_lang = tk.StringVar(value=LANG_NAMES[self.lang])
        self.cmb_lang = ttk.Combobox(grid, textvariable=self.var_lang, values=list(LANG_NAMES.values()), height=14,
                                     state="readonly")
        self.cmb_lang.grid(row=1, column=1, sticky="ew", pady=(self.px(6), 0))
        self.cmb_lang.bind("<<ComboboxSelected>>", self._on_language)
        links = ttk.Frame(s, style="Panel.TFrame")
        links.pack(fill="x", pady=(self.px(14), 0))
        self.lnk_bug = self._link(links, lambda: self._mail("Bug", bug=True))
        self.lnk_bug.pack(side="left")
        self.lnk_support = self._link(links, lambda: self._mail("Support"))
        self.lnk_support.pack(side="left", padx=(self.px(16), 0))

        # --- privacy tab
        p = self.tab_privacy
        self.var_share = tk.BooleanVar(value=self.cfg["share_data"])
        self.chk_share = ttk.Checkbutton(p, variable=self.var_share, command=self._on_share)
        self.chk_share.pack(anchor="w")
        wrap = W - self.px(52)
        self.lbl_share_info = ttk.Label(p, style="PanelMuted.TLabel", wraplength=wrap, justify="left")
        self.lbl_share_info.pack(fill="x", pady=(self.px(8), 0))
        self.lbl_share_state = ttk.Label(p, style="Panel.TLabel", wraplength=wrap, justify="left")
        self.lbl_share_state.pack(fill="x", pady=(self.px(10), 0))
        self.btn_delete = ttk.Button(p, command=self._on_delete, style="Panel.TButton")
        self.btn_delete.pack(anchor="w", pady=(self.px(10), 0))
        self.lnk_policy = self._link(p, self._open_policy, wrap=wrap)
        self.lnk_policy.pack(anchor="w", pady=(self.px(10), 0))
        self.lnk_privacy = self._link(p, lambda: self._mail("Support"), wrap=wrap)
        self.lnk_privacy.pack(anchor="w", pady=(self.px(6), 0))

        # --- statistics tab
        st = self.tab_stats
        self.lbl_today = ttk.Label(st, style="PanelStrong.TLabel", wraplength=wrap, justify="left")
        self.lbl_today.pack(fill="x")
        views = ttk.Frame(st, style="Panel.TFrame")
        views.pack(fill="x", pady=(self.px(8), 0))
        self.lnk_7 = self._link(views, lambda: self._stats_view(7))
        self.lnk_30 = self._link(views, lambda: self._stats_view(30))
        self.lnk_csv = self._link(views, self._export_csv)
        self.lnk_7.pack(side="left")
        self.lnk_30.pack(side="left", padx=(self.px(12), 0))
        self.lnk_csv.pack(side="right")
        self.chart_w, self.chart_h = wrap, self.px(116)
        self.chart = tk.Canvas(st, width=self.chart_w, height=self.chart_h, highlightthickness=0, bd=0)
        self.chart.pack(pady=(self.px(10), self.px(8)))
        legend = ttk.Frame(st, style="Panel.TFrame")
        legend.pack(fill="x")
        legend.columnconfigure(1, weight=1)
        self.legend = {}
        for row, cat in enumerate(CATS):
            dot = tk.Canvas(legend, width=self.px(10), height=self.px(10), highlightthickness=0, bd=0)
            dot.grid(row=row, column=0, padx=(0, self.px(8)), pady=self.px(1))
            name = ttk.Label(legend, style="Panel.TLabel")
            name.grid(row=row, column=1, sticky="w")
            value = ttk.Label(legend, style="PanelMuted.TLabel")
            value.grid(row=row, column=2, sticky="e")
            self.legend[cat] = (dot, name, value)
        self.lbl_week = ttk.Label(st, style="Panel.TLabel")
        self.lbl_week.pack(fill="x", pady=(self.px(6), 0))
        self.var_stats = tk.BooleanVar(value=self.cfg["keep_stats"])
        pv = self.tab_privacy                   # statistics switch lives with the other data choices
        ttk.Separator(pv).pack(fill="x", pady=(self.px(14), self.px(10)))
        self.chk_stats = ttk.Checkbutton(pv, variable=self.var_stats, command=self._on_keep_stats)
        self.chk_stats.pack(anchor="w")
        self.lbl_stats_note = ttk.Label(pv, style="PanelMuted.TLabel", wraplength=wrap, justify="left")
        self.lbl_stats_note.pack(fill="x", pady=(self.px(4), 0))
        self.btn_stats_delete = ttk.Button(pv, command=self._on_stats_delete, style="Panel.TButton")
        self.btn_stats_delete.pack(anchor="w", pady=(self.px(8), 0))
        self.tabs.bind("<<NotebookTabChanged>>", lambda e: (self._draw_stats(), self._fit()))

        # --- pro tab
        pr, px = self.tab_pro, self.px
        self.lbl_pro_state = ttk.Label(pr, style="PanelStrong.TLabel", wraplength=wrap, justify="left")
        self.lbl_pro_state.pack(fill="x")
        self.lbl_pro_pitch = ttk.Label(pr, style="PanelMuted.TLabel", wraplength=wrap, justify="left")
        self.lbl_pro_pitch.pack(fill="x", pady=(px(6), 0))
        self.btn_buy = ttk.Button(pr, style="Accent.TButton", command=lambda: self._open(pro.PRO_BUY_URL))
        self.btn_buy.pack(anchor="w", pady=(px(10), 0))
        keyrow = self.keyrow = ttk.Frame(pr, style="Panel.TFrame")
        keyrow.pack(fill="x", pady=(px(10), 0))
        self.lbl_key = ttk.Label(keyrow, style="Panel.TLabel")
        self.lbl_key.pack(side="left")
        self.var_key = tk.StringVar()
        self.ent_key = ttk.Entry(keyrow, textvariable=self.var_key, width=18)
        self.ent_key.pack(side="left", fill="x", expand=True, padx=(px(8), px(8)))
        self.ent_key.bind("<Return>", lambda e: self._on_key())
        self.btn_key = ttk.Button(keyrow, style="Panel.TButton", command=self._on_key)
        self.btn_key.pack(side="left")
        self.lnk_manage = self._link(pr, lambda: self._open(pro.PRO_PORTAL_URL))
        self.lnk_manage.pack(anchor="w", pady=(px(8), 0))
        self.pro_sep = ttk.Separator(pr)
        self.pro_sep.pack(fill="x", pady=(px(14), px(10)))

        box = self.pro_box = ttk.Frame(pr, style="Panel.TFrame")
        box.pack(fill="x")
        self.lbl_locked = ttk.Label(box, style="PanelMuted.TLabel")
        self.lbl_locked.pack(anchor="w", pady=(0, px(6)))
        g = self.pro_grid = ttk.Frame(box, style="Panel.TFrame")
        g.pack(fill="x")
        self.lbl_timers = ttk.Label(g, style="Panel.TLabel")
        self.lbl_timers.grid(row=0, column=0, sticky="w", padx=(0, px(10)))
        self.cmb_preset = ttk.Combobox(g, state="readonly", width=20)
        self.cmb_preset.grid(row=0, column=1, columnspan=2, sticky="ew")
        self.cmb_preset.bind("<<ComboboxSelected>>", self._on_preset)
        self.time_vars, self.time_spins, self.time_lbls, self.unit_lbls = {}, {}, {}, []
        for row, key in enumerate(("work_min", "break_min", "idle_min"), start=1):
            lbl = ttk.Label(g, style="PanelMuted.TLabel")
            lbl.grid(row=row, column=0, sticky="w", padx=(px(12), px(10)), pady=(px(6), 0))
            var = tk.StringVar(value=str(self.cfg[key]))
            spin = ttk.Spinbox(g, from_=LIMITS[key][0], to=LIMITS[key][1], width=4, textvariable=var,
                               command=self._on_times, justify="right")
            spin.grid(row=row, column=1, sticky="w", pady=(px(6), 0))
            unit = ttk.Label(g, style="PanelMuted.TLabel")
            unit.grid(row=row, column=2, sticky="w", padx=(px(6), 0), pady=(px(6), 0))
            self.unit_lbls.append(unit)
            for ev in ("<Return>", "<FocusOut>", "<KP_Enter>"):
                spin.bind(ev, self._on_times)
            self.time_vars[key], self.time_spins[key], self.time_lbls[key] = var, spin, lbl
        g.columnconfigure(2, weight=1)
        self.pro_checks = {}
        for key in ("smart_pause", "snooze", "filter_auto", "exercises"):
            var = tk.BooleanVar(value=self.cfg[key])
            chk = ttk.Checkbutton(box, variable=var, style="Wrap.TCheckbutton",
                                  command=lambda k=key, v=var: self._on_pro_check(k, v))
            chk.pack(anchor="w", pady=(px(8), 0))
            self.pro_checks[key] = (var, chk)
            if key == "filter_auto":                       # hours of the evening filter
                hrs = ttk.Frame(box, style="Panel.TFrame")
                hrs.pack(anchor="w", padx=(px(26), 0), pady=(px(2), 0))
                self.hour_vars, self.hour_spins = {}, {}
                for i, hk in enumerate(("filter_from", "filter_to")):
                    hv = tk.StringVar(value=f"{self.cfg[hk]:02d}")
                    hs = ttk.Spinbox(hrs, from_=0, to=23, width=3, textvariable=hv, wrap=True, format="%02.0f",
                                     command=self._on_hours, justify="right")
                    hs.pack(side="left")
                    for ev in ("<Return>", "<FocusOut>", "<KP_Enter>"):
                        hs.bind(ev, self._on_hours)
                    ttk.Label(hrs, text=":00" + ("  –  " if i == 0 else ""), style="Panel.TLabel").pack(side="left")
                    self.hour_vars[hk], self.hour_spins[hk] = hv, hs
        snd = ttk.Frame(box, style="Panel.TFrame")
        snd.pack(fill="x", pady=(px(10), 0))
        self.lbl_sound = ttk.Label(snd, style="Panel.TLabel")
        self.lbl_sound.pack(side="left", padx=(0, px(10)))
        self.cmb_sound = ttk.Combobox(snd, state="readonly", width=14)
        self.cmb_sound.pack(side="left")
        self.cmb_sound.bind("<<ComboboxSelected>>", self._on_sound)

        # --- sponsors tab
        sp = self.tab_sponsors
        self.lbl_thanks = ttk.Label(sp, style="PanelStrong.TLabel", wraplength=wrap, justify="left")
        self.lbl_thanks.pack(fill="x")
        self.sponsor_rows = []
        for name, logo in SPONSORS:
            img_lbl = ttk.Label(sp, style="Panel.TLabel")
            img_lbl.pack(anchor="w", pady=(self.px(14), self.px(4)))
            txt = ttk.Label(sp, style="PanelMuted.TLabel", wraplength=wrap, justify="left")
            txt.pack(fill="x")
            self.sponsor_rows.append((name, logo, img_lbl, txt))
        self.lbl_join = ttk.Label(sp, style="PanelMuted.TLabel", wraplength=wrap, justify="left")
        self.lbl_join.pack(fill="x", pady=(self.px(16), 0))
        self.btn_sponsor = ttk.Button(sp, command=lambda: self._mail("Partner"), style="Panel.TButton")
        self.btn_sponsor.pack(anchor="w", pady=(self.px(8), 0))
        ttk.Label(sp, text=CONTACT_EMAIL, style="PanelMuted.TLabel").pack(anchor="w", pady=(self.px(4), 0))

        foot = ttk.Frame(main)
        foot.pack(fill="x", pady=(self.px(12), 0))
        self.lbl_hint = ttk.Label(foot, style="Muted.TLabel", wraplength=W - self.px(150), justify="left")
        self.lbl_hint.pack(side="left")
        self.btn_quit = ttk.Button(foot, command=self.quit)
        self.btn_quit.pack(side="right")

    def apply_language(self):
        self.root.title("Breyek 2.0" + (" (demo)" if DEMO else ""))
        for tab, key in ((self.tab_settings, "tab_settings"), (self.tab_stats, "tab_stats"), (self.tab_pro, "tab_pro"),
                         (self.tab_privacy, "tab_privacy"), (self.tab_sponsors, "tab_sponsors")):
            self.tabs.tab(tab, text=self.t(key))
        self.chk_autostart.configure(text=self.t("autostart"))
        self.chk_corner.configure(text=self.t("corner_timer"))
        self.chk_screen.configure(text=self.t("screen_watch"))
        self.chk_media.configure(text=self.t("pause_media"))
        self.chk_filter.configure(text=self.t("eye_filter"))
        self.lbl_strength.configure(text=self.t("filter_strength"))
        self.lbl_theme.configure(text=self.t("theme"))
        self.lbl_lang.configure(text=self.t("language"))
        self.cmb_theme.configure(values=[self.t("theme_" + c) + (" (Pro)" if c in PRO_THEMES and not self.pro else "")
                                         for c in THEMES])
        self.cmb_theme.current(THEMES.index(self.cfg["theme"]))
        self.chk_share.configure(text=self.t("share_data"))
        self.lbl_share_info.configure(text=self.t("share_info") + "\n\n" + self.t("share_activity"))
        self.btn_delete.configure(text=self.t("delete_data"))
        self.lbl_thanks.configure(text=self.t("sponsors_thanks"))
        for name, logo, img_lbl, txt in self.sponsor_rows:
            txt.configure(text=self.t("sponsor_line", name=name))
        self.lbl_join.configure(text=self.t("sponsors_join"))
        self.btn_sponsor.configure(text=self.t("sponsor_cta"))
        self.lnk_bug.configure(text=self.t("contact_bug"))
        self.lnk_support.configure(text=self.t("contact_support"))
        self.lnk_privacy.configure(text=self.t("privacy_contact", email=CONTACT_EMAIL))
        self.lnk_policy.configure(text=self.t("policy_link"))
        self.chk_stats.configure(text=self.t("stats_keep"))
        self.lbl_stats_note.configure(text=self.t("stats_note"))
        self.btn_stats_delete.configure(text=self.t("stats_delete"))
        for cat, (dot, name, value) in self.legend.items():
            name.configure(text=self.t("cat_" + cat))
        self.lnk_7.configure(text=self.t("stats_7"))
        self.lnk_30.configure(text=self.t("stats_30") + ("" if self.pro else " (Pro)"))
        self.lnk_csv.configure(text=self.t("stats_export") + ("" if self.pro else " (Pro)"))
        self.lbl_pro_state.configure(text=self.t("pro_active" if self.pro else "pro_free"))
        self.lbl_pro_pitch.configure(text=self.t("pro_pitch"))
        self.btn_buy.configure(text=self.t("pro_buy"))
        self.lbl_key.configure(text=self.t("pro_key"))
        self.btn_key.configure(text=self.t("pro_remove" if self.pro else "pro_activate"))
        self.lnk_manage.configure(text=self.t("pro_manage"))
        self.lbl_locked.configure(text=self.t("pro_locked"))
        self.lbl_timers.configure(text=self.t("pro_timers"))
        self.cmb_preset.configure(values=[self.t("preset_" + k) for k in (*PRESETS, "custom")])
        self.cmb_preset.current([*PRESETS, "custom"].index(self.cfg["preset"]))
        for key, lbl in self.time_lbls.items():
            lbl.configure(text=self.t("t_" + key[:-4]))
        unit = self.t("hm").split("{m}")[-1].strip() or "min"           # "min" in the user's language
        for u in self.unit_lbls:
            u.configure(text=unit)
        for key, (var, chk) in self.pro_checks.items():
            chk.configure(text=self.t(key))
        self.lbl_sound.configure(text=self.t("sound"))
        self.cmb_sound.configure(values=[self.t("sound_" + k) for k in pro.SOUNDS])
        self.cmb_sound.current(pro.SOUNDS.index(self.cfg["sound"]))
        self.lbl_hint.configure(text=self.t("hint_close"))
        self.btn_quit.configure(text=self.t("quit"))
        self._update_share_state()
        self._draw_stats()

    def _update_share_state(self):
        if not self.cfg["share_data"]:
            text = ""
        else:
            day = self.usage.today()
            text = self.t("share_today", breaks=day["breaks"], minutes=day["active_min"])
            if not TELEMETRY_URL:
                text += "\n" + self.t("share_local")
        self.lbl_share_state.configure(text=text)
        if text:
            self.lbl_share_state.pack(fill="x", pady=(self.px(10), 0), before=self.btn_delete)
        else:
            self.lbl_share_state.pack_forget()
        self._fit()

    def _fit(self):
        """Window height follows the open tab instead of the tallest one."""
        tabs = [self.root.nametowidget(t) for t in self.tabs.tabs()]
        self.root.update_idletasks()
        h = self.root.nametowidget(self.tabs.select()).winfo_reqheight()
        w = max(t.winfo_reqwidth() for t in tabs)          # fixed width, so the window never jumps sideways
        if (int(self.tabs.cget("height")), int(self.tabs.cget("width"))) != (h, w):
            self.tabs.configure(height=h, width=w)

    # ------------------------------------------------- settings handlers
    def _on_language(self, event=None):
        for code, name in LANG_NAMES.items():
            if name == self.var_lang.get():
                self.lang = self.cfg["language"] = code
                save_config(self.cfg)
        self.apply_language()
        self.cmb_lang.selection_clear()

    def _on_autostart(self):
        wanted = self.var_autostart.get()
        try:
            set_autostart(wanted)
        except (OSError, RuntimeError):
            self.var_autostart.set(not wanted)
            messagebox.showerror(self.t("error_title"), self.t("error_autostart"))

    def _on_corner(self):
        self.cfg["corner_timer"] = self.var_corner.get()
        save_config(self.cfg)

    def _link(self, parent, command, wrap=None):
        label = ttk.Label(parent, style="Link.TLabel", cursor="hand2", wraplength=wrap or 0, justify="left")
        label.bind("<Button-1>", lambda e: command())
        return label

    def _mail(self, tag, bug=False):
        """Opens the user's mail app with the subject already tagged ([Bug], [Support], [Partner])."""
        body = ""
        if bug:
            body = (f"\n\n---\nBreyek {VERSION}{' demo' if DEMO else ''}, language {self.lang}, "
                    f"Windows {sys.getwindowsversion().major}.{sys.getwindowsversion().build}"
                    if hasattr(sys, "getwindowsversion") else f"\n\n---\nBreyek {VERSION}")
        query = urllib.parse.urlencode({"subject": f"[{tag}] Breyek", "body": body}, quote_via=urllib.parse.quote)
        try:
            webbrowser.open(f"mailto:{CONTACT_EMAIL}?{query}")
        except Exception:
            pass

    def _on_keep_stats(self):
        self.cfg["keep_stats"] = bool(self.var_stats.get())
        save_config(self.cfg)

    def _on_stats_delete(self):
        self.stats.delete()
        self._draw_stats()
        messagebox.showinfo("Breyek", self.t("stats_deleted"))

    def _draw_stats(self):
        """Last 7 (Pro: 30) days as stacked bars (hours per activity type) + legend with the totals."""
        if not hasattr(self, "chart"):
            return
        c, cv, hm, n = self.c, self.chart, self.t("hm"), self.stats_n
        for lnk, v in ((self.lnk_7, 7), (self.lnk_30, 30)):
            lnk.configure(style="LinkOn.TLabel" if v == n else "Link.TLabel")
        week = self.stats.last(n)
        totals = [sum(d.get(k, 0) for k in CATS) for _, d in week]
        today = week[-1][1]
        self.lbl_today.configure(text=self.t("stats_today", time=fmt_hm(totals[-1], hm), breaks=today.get("breaks", 0)))
        self.lbl_week.configure(text=self.t("stats_week" if n == 7 else "stats_month", time=fmt_hm(sum(totals), hm)))
        for cat, (dot, name, value) in self.legend.items():
            dot.configure(bg=c["panel"])
            dot.delete("all")
            dot.create_oval(1, 1, self.px(9), self.px(9), fill=CAT_COLORS[cat], outline="")
            value.configure(text=fmt_hm(sum(d.get(cat, 0) for _, d in week), hm))

        cv.configure(bg=c["panel"])
        cv.delete("all")
        W, H, left, bottom = self.chart_w, self.chart_h, self.px(30), self.px(18)
        top_h = max(1, math.ceil(max(totals) / 3600))          # whole hours on the axis
        step = 1 if top_h <= 4 else 2 if top_h <= 8 else 4
        top_h = math.ceil(top_h / step) * step
        plot = H - bottom - self.px(6)
        y_of = lambda secs: H - bottom - plot * secs / (top_h * 3600)
        small = (FONT_TXT, -self.px(11))
        for hour in range(0, top_h + 1, step):
            y = y_of(hour * 3600)
            cv.create_line(left, y, W, y, fill=c["line"])
            cv.create_text(left - self.px(6), y, text=f"{hour} h", anchor="e", fill=c["muted"], font=small)
        names = self.t("weekdays").split(",")
        slot = (W - left) / n
        bar = slot * 0.56
        for i, (date, d) in enumerate(week):
            x0 = left + i * slot + (slot - bar) / 2
            acc = 0
            for cat in CATS:
                secs = d.get(cat, 0)
                if secs >= 30:
                    cv.create_rectangle(x0, y_of(acc + secs), x0 + bar, y_of(acc), fill=CAT_COLORS[cat], outline="")
                    acc += secs
            if n == 7:
                label = names[date.weekday()] if len(names) == 7 else date.strftime("%d")
            else:
                label = str(date.day) if (n - 1 - i) % 5 == 0 else ""     # every 5th day, ending today
            if label:
                cv.create_text(x0 + bar / 2, H - bottom + self.px(9), text=label, font=small,
                               fill=c["fg"] if i == n - 1 else c["muted"])

    # ------------------------------------------------- Breyek Pro
    @property
    def pro(self):
        return self.license.active

    def _apply_pro(self):
        """Turns the Pro features on or off everywhere (after a key is added, removed or re-checked)."""
        on, px = self.pro, self.px
        if on and not DEMO:
            self.work_s, self.break_s, self.idle_s = (self.cfg[k] * 60 for k in ("work_min", "break_min", "idle_min"))
        else:
            self.work_s, self.idle_s, self.break_s = self.base_timing
        self.stats.keep_days = 365 if on else 60
        if not on:
            self.stats_n = 7
            if self.cfg["theme"] in PRO_THEMES:
                self.cfg["theme"] = "system"
                save_config(self.cfg)
                if self._theme_applied:
                    self.apply_theme()
        for var, chk in self.pro_checks.values():
            chk.state(["!disabled"] if on else ["disabled"])
        for w in (*self.time_spins.values(), *self.hour_spins.values()):
            custom = w not in self.time_spins.values() or self.cfg["preset"] == "custom"
            w.state(["!disabled"] if on and custom else ["disabled"])
        for cmb in (self.cmb_preset, self.cmb_sound):
            cmb.state(["!disabled", "readonly"] if on else ["disabled"])
        for w in (self.lbl_pro_pitch, self.btn_buy, self.lnk_manage, self.lbl_locked):
            w.pack_forget()
        if on:
            self.lnk_manage.pack(anchor="w", pady=(px(8), 0), before=self.pro_sep)
            key = self.license.data["key"]
            self.var_key.set("•••• " + key[-4:] if len(key) > 4 else key)
            self.ent_key.state(["readonly"])
        else:
            self.lbl_pro_pitch.pack(fill="x", pady=(px(6), 0), before=self.keyrow)
            self.btn_buy.pack(anchor="w", pady=(px(10), 0), before=self.keyrow)
            self.lbl_locked.pack(anchor="w", pady=(0, px(6)), before=self.pro_grid)
            self.ent_key.state(["!readonly"])
        self._sync_filter_widgets()
        if self._theme_applied:                      # after start-up: refresh texts and window size
            self.apply_language()

    def _open(self, url):
        """Polar page; until the links are set in pro.py, an email to us instead of a dead button."""
        if not url:
            return self._mail("Pro")
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _on_key(self):
        if self.pro:
            self.license.remove()
            self.var_key.set("")
            self._apply_pro()
            return
        key = self.var_key.get().strip()
        if not key:
            return
        self.btn_key.state(["disabled"])
        box = {}
        threading.Thread(target=lambda: box.setdefault("r", self.license.set_key(key)), daemon=True).start()

        def wait():                               # the check runs in the background, the window stays usable
            if "r" not in box:
                self.root.after(150, wait)
                return
            self.btn_key.state(["!disabled"])
            if box["r"] is False:
                messagebox.showerror("Breyek", self.t("pro_bad_key"))
            elif box["r"] is None:
                messagebox.showerror("Breyek", self.t("pro_offline"))
            self._apply_pro()
        wait()

    def _go_pro(self):
        self.tabs.select(self.tab_pro)

    def _on_preset(self, event=None):
        key = [*PRESETS, "custom"][self.cmb_preset.current()]
        self.cfg["preset"] = key
        if key in PRESETS:
            for k, v in zip(("work_min", "break_min", "idle_min"), PRESETS[key]):
                self.cfg[k] = v
                self.time_vars[k].set(str(v))
        save_config(self.cfg)
        self.cmb_preset.selection_clear()
        self._apply_pro()

    def _on_times(self, event=None):
        for key, var in self.time_vars.items():
            digits = "".join(ch for ch in var.get() if ch.isdigit())
            lo, hi = LIMITS[key]
            self.cfg[key] = max(lo, min(hi, int(digits))) if digits else self.cfg[key]
            var.set(str(self.cfg[key]))
        save_config(self.cfg)
        self._apply_pro()

    def _on_hours(self, event=None):
        for key, var in self.hour_vars.items():
            digits = "".join(ch for ch in var.get() if ch.isdigit())
            self.cfg[key] = max(0, min(23, int(digits))) if digits else self.cfg[key]
            var.set(f"{self.cfg[key]:02d}")
        save_config(self.cfg)

    def _on_pro_check(self, key, var):
        self.cfg[key] = bool(var.get())
        save_config(self.cfg)
        self._sync_filter_widgets()

    def _on_sound(self, event=None):
        self.cfg["sound"] = pro.SOUNDS[self.cmb_sound.current()]
        save_config(self.cfg)
        self.cmb_sound.selection_clear()
        pro.play(self.cfg["sound"], CONFIG_DIR)          # a preview

    def _stats_view(self, n):
        if n != 7 and not self.pro:
            return self._go_pro()
        self.stats_n = n
        self._draw_stats()

    def _export_csv(self):
        if not self.pro:
            return self._go_pro()
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".csv", initialfile="breyek-stats.csv",
                                            filetypes=[("CSV", "*.csv")])
        if path:
            try:
                self.stats.export_csv(path)
            except OSError as e:
                messagebox.showerror("Breyek", str(e))

    def _filter_scheduled(self):
        if not (self.pro and self.cfg["filter_auto"]):
            return False
        a, b, h = self.cfg["filter_from"], self.cfg["filter_to"], time.localtime().tm_hour
        return a <= h < b if a < b else (h >= a or h < b) if a > b else False

    def _should_hold(self, now):
        """Pro smart pause: no break during a call or a full-screen app, but never longer than 10 min."""
        if not (self.pro and self.cfg["smart_pause"]):
            return False
        if self.hold_since is not None and now - self.hold_since >= HOLD_MAX_S:
            return False
        if now >= self._next_busy:
            self._next_busy = now + 2.0
            self._busy = self.fullscreen or pro.in_call()
        return self._busy

    def _snoozes_left(self):
        today = datetime.date.today().isoformat()
        if self.cfg["snooze_day"] != today:
            self.cfg["snooze_day"], self.cfg["snooze_used"] = today, 0
        return max(0, SNOOZES_PER_DAY - self.cfg["snooze_used"])

    def _snooze(self):
        if self.state is State.RUNNING and self._snoozes_left():
            self.cfg["snooze_used"] += 1
            save_config(self.cfg)
            self.run_start += SNOOZE_S
            self._log("SNOOZED 5 min")
        self._toast(None)

    def _toast(self, remaining):
        """Pro: small card above the corner timer 30 s before a break, with a snooze button."""
        if remaining is None:
            if self.toast:
                self.toast[0].destroy()
                self.toast = None
            return
        c, px = self.c, self.px
        if self.toast is None:
            win = tk.Toplevel(self.root, bg=c["panel"], highlightthickness=1, highlightbackground=c["line"])
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            box = ttk.Frame(win, padding=(px(14), px(10)), style="Panel.TFrame")
            box.pack()
            lbl = ttk.Label(box, style="PanelStrong.TLabel")
            lbl.pack(anchor="w")
            btn = ttk.Button(box, style="Panel.TButton", command=self._snooze)
            btn.pack(anchor="w", pady=(px(6), 0))
            self.toast = (win, lbl, btn)
        win, lbl, btn = self.toast
        left = self._snoozes_left()
        lbl.configure(text=self.t("break_soon", time=fmt(remaining)))
        btn.configure(text=self.t("snooze_btn", n=left))
        btn.state(["!disabled"] if left else ["disabled"])
        win.update_idletasks()
        l, t, r, b = get_work_area(self.root)
        lift = (self.corner.win.winfo_height() + px(8)) if self.corner.visible else 0
        win.geometry(f"+{r - win.winfo_reqwidth() - 12}+{b - win.winfo_reqheight() - 12 - lift}")
        win.lift()

    def _on_media(self):
        self.cfg["pause_media"] = bool(self.var_media.get())
        save_config(self.cfg)

    def _on_screen(self):
        self.cfg["screen_watch"] = bool(self.var_screen.get())
        self.screen_on = self.cfg["screen_watch"] and self.screen is not None
        self.last_screen = 0.0
        if self.screen:
            self.screen.reset()
        save_config(self.cfg)

    def _sync_filter_widgets(self):
        on = self.var_filter.get() or (self.pro and self.cfg["filter_auto"])
        for w in (self.scale_w, self.spin_pct):
            w.state(["!disabled"] if on else ["disabled"])

    def _on_filter(self):
        self.cfg["eye_filter"] = bool(self.var_filter.get())
        self._sync_filter_widgets()
        save_config(self.cfg)

    def _on_strength(self, value):
        try:
            exact = float(value)
        except ValueError:
            return
        pct = max(FILTER_MIN, min(FILTER_MAX, int(round(exact))))
        self.cfg["filter_strength"] = pct
        self.var_pct.set(str(pct))
        if abs(exact - pct) > 0.01:
            self.scale_w.set(pct)          # whole percents only

    def _on_pct_typed(self, event=None):
        digits = "".join(ch for ch in self.var_pct.get() if ch.isdigit())
        pct = max(FILTER_MIN, min(FILTER_MAX, int(digits))) if digits else self.cfg["filter_strength"]
        self.scale_w.set(pct)              # calls _on_strength, which also tidies the box
        self.var_pct.set(str(pct))
        save_config(self.cfg)

    def _on_share(self):
        self.cfg["share_data"] = bool(self.var_share.get())
        if not self.cfg["share_data"]:
            self.usage.delete()            # opted out: what was collected is gone too
        save_config(self.cfg)
        self._update_share_state()

    def _on_delete(self):
        self.usage.delete()
        self._update_share_state()
        messagebox.showinfo("Breyek", self.t("data_deleted"))

    def _on_theme(self, event=None):
        index = self.cmb_theme.current()
        if 0 <= index < len(THEMES) and THEMES[index] in PRO_THEMES and not self.pro:
            self.cmb_theme.current(THEMES.index(self.cfg["theme"]))
            self.cmb_theme.selection_clear()
            return self._go_pro()
        if 0 <= index < len(THEMES):
            self.cfg["theme"] = THEMES[index]
            save_config(self.cfg)
            self.apply_theme()
        self.cmb_theme.selection_clear()

    def _resolved_theme(self):
        if self.cfg["theme"] == "system":
            return "dark" if system_prefers_dark() else "light"
        return self.cfg["theme"]

    def apply_theme(self):
        """Warm night colours on the ttk 'clam' theme."""
        name = self._resolved_theme()
        self._theme_applied = name
        c = self.c = PALETTES[name]
        st = ttk.Style(self.root)
        st.theme_use("clam")
        f, fb = (FONT_TXT, -self.px(13)), (FONT_TXT, -self.px(13), "bold")
        self.root.configure(bg=c["bg"])
        st.configure(".", background=c["bg"], foreground=c["fg"], fieldbackground=c["panel"], font=f,
                     bordercolor=c["line"], lightcolor=c["bg"], darkcolor=c["bg"], troughcolor=c["track"],
                     focuscolor=c["accent"], selectbackground=c["accent"], selectforeground=c["accent_fg"])
        st.configure("TFrame", background=c["bg"])
        st.configure("Panel.TFrame", background=c["panel"])
        st.configure("TSeparator", background=c["line"])
        st.configure("TLabel", background=c["bg"], foreground=c["fg"])
        st.configure("Brand.TLabel", font=(FONT_NUM, -self.px(22)), foreground=c["fg"])
        st.configure("Muted.TLabel", foreground=c["muted"], font=(FONT_TXT, -self.px(12)))
        st.configure("Panel.TLabel", background=c["panel"], foreground=c["fg"])
        st.configure("PanelMuted.TLabel", background=c["panel"], foreground=c["muted"])
        st.configure("PanelStrong.TLabel", background=c["panel"], foreground=c["fg"], font=fb)
        st.configure("Link.TLabel", background=c["panel"], foreground=c["accent"],
                     font=(FONT_TXT, -self.px(12), "underline"))
        st.configure("TNotebook", background=c["bg"], borderwidth=0, tabmargins=(0, 0, 0, 0))
        st.configure("TNotebook.Tab", background=c["bg"], foreground=c["muted"], borderwidth=0,
                     padding=(self.px(9), self.px(7)), lightcolor=c["bg"], bordercolor=c["bg"])
        st.map("TNotebook.Tab", background=[("selected", c["panel"])], foreground=[("selected", c["fg"])],
               lightcolor=[("selected", c["panel"])], bordercolor=[("selected", c["panel"])],
               expand=[("selected", (0, 0, 0, 0))])
        st.configure("TCheckbutton", background=c["panel"], foreground=c["fg"], indicatorbackground=c["bg"],
                     indicatormargin=(0, 0, self.px(8), 0), padding=(0, self.px(2)))
        st.map("TCheckbutton", background=[("active", c["panel"])],
               indicatorbackground=[("selected", c["accent"]), ("!selected", c["bg"])],
               indicatorforeground=[("selected", c["accent_fg"]), ("!selected", c["fg"])],
               foreground=[("disabled", c["muted"])])
        st.configure("TButton", background=c["panel"], foreground=c["fg"], bordercolor=c["line"],
                     padding=(self.px(14), self.px(5)), relief="flat")
        st.map("TButton", background=[("active", c["line"])])
        st.configure("Panel.TButton", background=c["bg"])          # a button inside a panel
        st.configure("Accent.TButton", background=c["accent"], foreground=c["accent_fg"], bordercolor=c["accent"])
        st.map("Accent.TButton", background=[("active", c["fg"])])
        st.configure("LinkOn.TLabel", background=c["panel"], foreground=c["fg"], font=(FONT_TXT, -self.px(12), "bold"))
        st.configure("Wrap.TCheckbutton", wraplength=self.px(380) - self.px(80))
        st.configure("PanelBrand.TLabel", background=c["panel"], foreground=c["fg"], font=(FONT_NUM, -self.px(20)))
        st.configure("TCombobox", background=c["bg"], foreground=c["fg"], arrowcolor=c["fg"],
                     fieldbackground=c["bg"], selectbackground=c["bg"], selectforeground=c["fg"],
                     bordercolor=c["line"], padding=(self.px(6), self.px(3)))
        st.map("TCombobox", fieldbackground=[("readonly", c["bg"])], foreground=[("readonly", c["fg"])],
               selectbackground=[("readonly", c["bg"])], selectforeground=[("readonly", c["fg"])])
        st.configure("TSpinbox", foreground=c["fg"], fieldbackground=c["bg"], background=c["bg"],
                     arrowcolor=c["fg"], bordercolor=c["line"], lightcolor=c["bg"], darkcolor=c["bg"],
                     insertcolor=c["fg"], selectbackground=c["accent"], selectforeground=c["accent_fg"],
                     padding=(self.px(4), self.px(2)))
        st.map("TSpinbox", foreground=[("disabled", c["muted"])], fieldbackground=[("disabled", c["panel"])])
        st.configure("Horizontal.TScale", background=c["accent"], troughcolor=c["track"],
                     bordercolor=c["panel"], lightcolor=c["accent"], darkcolor=c["accent"])
        for opt, val in (("background", c["panel"]), ("foreground", c["fg"]),
                         ("selectBackground", c["accent"]), ("selectForeground", c["accent_fg"])):
            self.root.option_add(f"*TCombobox*Listbox.{opt}", val)
        for combo in (self.cmb_lang, self.cmb_theme):        # drop-down lists that already exist
            try:
                pop = self.root.tk.call("ttk::combobox::PopdownWindow", str(combo))
                self.root.tk.call(f"{pop}.f.l", "configure", "-background", c["panel"], "-foreground",
                                  c["fg"], "-selectbackground", c["accent"], "-selectforeground", c["accent_fg"])
            except tk.TclError:
                pass
        self.ring.configure(bg=c["bg"])
        self._ring_key = None                    # redraw the ring in the new colours
        self.ring.itemconfigure(self.ring_time, fill=c["fg"])
        self.sponsor_imgs = []
        for name, logo, img_lbl, txt in self.sponsor_rows:
            img = load_image(logo, self._theme_applied)
            self.sponsor_imgs.append(img)
            img_lbl.configure(image=img or "", text="" if img else name)
        self.corner.set_colors(c) if hasattr(self, "corner") else None
        set_titlebar(self.root, name in DARK_THEMES, c["bg"], c["fg"])

    def _update_ui(self, now):
        if self.state is State.WAITING:
            status, secs, total = self.t("status_waiting"), self.work_s, self.work_s
        elif self.state is State.RUNNING:
            status, secs, total = self.t("status_running"), self.work_s - (now - self.run_start), self.work_s
            if self.hold_since is not None:
                status, secs = self.t("break_held"), 0
        else:
            status, secs, total = self.t("status_locked"), self.lock_end - now, self.break_s
        active = self.state is not State.WAITING
        share = max(0.0, min(1.0, secs / total)) if total else 0
        key = (round(share * 1440), active, self._theme_applied)
        if key != self._ring_key:
            self._ring_key = key
            self.ring_img = ring_image(self.ring_d, self.ring_w, share, self.c["track"],
                                       self.c["accent"] if active else self.c["muted"], self.c["bg"])
            self.ring.itemconfigure(self.ring_bg, image=self.ring_img)
        self.ring.itemconfigure(self.ring_time, text=fmt(secs))
        self.lbl_status.configure(text=status)
        self.lbl_screen.configure(text=self._screen_text())

        show_corner = self.cfg["corner_timer"] and self.state is not State.LOCKED
        self.corner.set_visible(show_corner)
        if show_corner:
            self.corner.set_text(fmt(secs), active)

    def _screen_text(self):
        if self.screen is None or self.screen.unavailable:
            return self.t("screen_unavailable")
        if not self.screen_on:
            return self.t("screen_off")
        text = self.t("screen_moving") if self.screen.moving else self.t("screen_still")
        return f"{text} ({self.screen.last_fraction * 100:.1f}%)"

    # ------------------------------------------------- activity
    def _poll_input(self, now):
        """Any keyboard/mouse input in ANY app counts; so does a moving screen (video)."""
        idle = seconds_since_last_input()
        if idle is not None and self.state is not State.LOCKED:
            if now - idle > self._input_at + 0.05:             # new input since the last tick
                pos = cursor_pos()
                if pos != self._cursor or mouse_button_down():
                    self.last_mouse = now
                else:
                    self.last_kb = now                       # input without the mouse: the keyboard
                self._cursor = pos
            self._input_at = now - idle
            self.last_input = max(now - idle, self.last_screen)

    def _activity(self, now):
        """What the user is probably doing right now (only the kind of input, never its content)."""
        if now >= self._next_fs:
            self._next_fs, self.fullscreen = now + 1.0, foreground_fullscreen()
        kb, ms = now - self.last_kb < 3, now - self.last_mouse < 3
        if kb or ms:
            return "game" if self.fullscreen else "work" if kb else "browse"
        return "watch" if now - self.last_screen < 3 else "read"

    def _poll_screen(self, now):
        if not self.screen_on or self.state is State.LOCKED or now < self._next_screen:
            return
        self._next_screen = now + SCREEN_EVERY_S
        try:
            self.screen.sample()
            if self.screen.moving:
                self.last_screen = now
        except Exception:
            pass          # never let screen detection break the timer

    # ------------------------------------------------- input blocking
    CTRL = {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}
    ALT = {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr}
    SHIFT = {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r}

    def _block_press(self, key):
        self._held.add(key)
        if getattr(key, "vk", None) == 0x51 and self._held & self.CTRL and self._held & self.ALT \
                and self._held & self.SHIFT:
            self.emergency = True

    def _start_blockers(self):
        self._held.clear()
        self.blockers = [mouse.Listener(suppress=True),
                         keyboard.Listener(on_press=self._block_press, on_release=self._held.discard,
                                           suppress=True)]
        for listener in self.blockers:
            listener.start()

    def _stop_blockers(self):
        for listener in self.blockers:
            try:
                listener.stop()
            except Exception:
                pass
        self.blockers = []

    # ------------------------------------------------- state changes
    def _log(self, msg):
        try:
            print(time.strftime("[%H:%M:%S]"), msg, flush=True)
        except Exception:        # no console in the .exe build
            pass

    def _to_waiting(self, why):
        self.state = State.WAITING
        self.state_since = time.monotonic()
        self._log(f"WAITING ({why})")

    def _lock(self):
        self.state = State.LOCKED
        now = time.monotonic()
        self.lock_end = now + self.break_s
        self.next_tip_at, self.ex_index, self.current_dot = now, 0, False
        self.corner.set_visible(False)
        self._toast(None)
        if self.pro:
            pro.play(self.cfg["sound"], CONFIG_DIR)
        if self.cfg["pause_media"]:      # before the input blockers: the media key must get through
            self.media.pause(video_likely=now - self.last_screen < 5)
        sponsor = None if self.pro else self.t("supported_by")        # Pro: no sponsors on the break screen
        self.overlays = [Overlay(self.root, *m, self.t("break_title"), sponsor, self.lang)
                         for m in get_monitors(self.root)]
        self._start_blockers()
        self._log("LOCKED - input blocked")

    def _unlock(self):
        self._stop_blockers()
        for o in self.overlays:
            o.close()
        self.overlays = []
        self.media.resume()
        if self.pro:
            pro.play(self.cfg["sound"], CONFIG_DIR, ending=True)
        self.license.refresh(lambda: setattr(self, "_lic_dirty", True))
        if self.screen:
            self.screen.reset()          # the cover changed the screen: start fresh
        self.last_screen = 0.0
        self.usage.add_break()
        self.stats.add_break()
        self._update_share_state()
        self._to_waiting("break finished")

    # ------------------------------------------------- main loop
    def _tick(self):
        now = time.monotonic()
        step, self._last_tick = now - self._last_tick, now
        self._poll_screen(now)
        self._poll_input(now)

        if self.state is State.WAITING:
            if self.last_input > self.state_since:
                self.state, self.run_start = State.RUNNING, now
                self._log(f"RUNNING - {fmt(self.work_s)} until break")
        elif self.state is State.RUNNING:
            self.usage.add_active(step)
            self.stats.add(self._activity(now), step)
            remaining = self.work_s - (now - self.run_start)
            if now - self.last_input >= self.idle_s:
                self.hold_since = None
                self._to_waiting(f"no input for {fmt(self.idle_s)}")
            elif remaining <= 0:
                if self._should_hold(now):
                    if self.hold_since is None:
                        self.hold_since = now
                        self._log("HOLD - call or full-screen app")
                else:
                    self.hold_since = None
                    self._lock()
        if self.state is State.RUNNING and self.pro and self.cfg["snooze"] and self.hold_since is None \
                and 0 < self.work_s - (now - self.run_start) <= WARN_S:
            self._toast(math.ceil(self.work_s - (now - self.run_start)))
        elif self.toast:
            self._toast(None)
        if self.state is State.LOCKED:
            if self.emergency:
                self._log("EMERGENCY EXIT")
                self.quit()
                return
            remaining = math.ceil(self.lock_end - now)
            if remaining <= 0:
                self._unlock()
            else:
                if now >= self.next_tip_at:
                    if self.pro and self.cfg["exercises"]:          # Pro: guided exercises in order
                        key = EXERCISES[self.ex_index % len(EXERCISES)]
                        self.ex_index += 1
                        self.current_tip, self.current_dot = self.t(key), key == "ex_dot"
                    else:
                        self.current_tip = random.choice(TIPS.get(self.lang) or TIPS["en"])
                        self.current_dot = False
                    self.next_tip_at = now + TIP_ROTATE_SECONDS
                for o in self.overlays:
                    o.update(fmt(remaining), self.current_tip, self.current_dot)
                    o.keep_on_top()

        if self.cfg["theme"] == "system" and now >= self._next_theme_check:
            self._next_theme_check = now + 3.0
            if self._resolved_theme() != self._theme_applied:
                self.apply_theme()           # Windows switched between light and dark

        if self._lic_dirty:                          # the daily license check finished in the background
            self._lic_dirty = False
            self._apply_pro()
        refreshed = self.eyefilter.update(
            (self.cfg["eye_filter"] or self._filter_scheduled()) and self.cfg["filter_strength"] > 0
            and self.state is not State.LOCKED,
            self.cfg["filter_strength"], now)
        if refreshed and self.corner.visible:
            self.corner.win.lift()           # keep the small timer above the tint

        if now >= self._next_chart and self.tabs.select() == str(self.tab_stats):
            self._next_chart = now + 5.0
            self._draw_stats()
        self._update_ui(now)
        self.root.after(TICK_MS, self._tick)

    def quit(self):
        if self._quitting:
            return
        self._quitting = True
        self._stop_blockers()
        if self.overlays:
            self.media.resume()          # emergency exit during a break: give the video back
        for o in self.overlays:
            o.close()
        self.overlays = []
        self.stats.save()
        self._toast(None)
        self.corner.close()
        self.eyefilter.close()
        self.root.quit()

    def _open_policy(self):
        try:
            webbrowser.open(f"{PRIVACY_URL}?lang={'lt' if self.lang == 'lt' else 'en'}")
        except Exception:
            pass

    def _ask_consent(self):
        """First start (or a new policy version): nothing runs until the user agrees."""
        self.root.withdraw()
        c, px = self.c, self.px
        d = self.consent = tk.Toplevel(self.root, bg=c["panel"])
        d.title("Breyek")
        d.resizable(False, False)
        try:
            d.iconbitmap(resource_path(ICON_FILE))
        except tk.TclError:
            pass
        d.protocol("WM_DELETE_WINDOW", self.root.quit)
        box = ttk.Frame(d, padding=(px(28), px(24), px(28), px(22)), style="Panel.TFrame")
        box.pack(fill="both", expand=True)
        wrap = px(380)
        ttk.Label(box, text=self.t("consent_title"), style="PanelBrand.TLabel").pack(anchor="w")
        ttk.Label(box, text=self.t("consent_text"), style="PanelMuted.TLabel", wraplength=wrap,
                  justify="left").pack(anchor="w", pady=(px(10), 0))
        self._link(box, self._open_policy).configure(text=self.t("consent_read"))
        box.winfo_children()[-1].pack(anchor="w", pady=(px(12), 0))
        ttk.Separator(box).pack(fill="x", pady=(px(18), px(14)))
        share = tk.BooleanVar(value=False)                      # data sharing stays a separate, opt-in choice
        ttk.Checkbutton(box, text=self.t("share_data"), variable=share).pack(anchor="w")
        ttk.Label(box, text=self.t("consent_note"), style="PanelMuted.TLabel", wraplength=wrap - px(26),
                  justify="left").pack(anchor="w", padx=(px(26), 0))
        row = ttk.Frame(box, style="Panel.TFrame")
        row.pack(fill="x", pady=(px(22), 0))

        def agree():
            self.cfg["policy"], self.cfg["share_data"] = POLICY_VERSION, bool(share.get())
            save_config(self.cfg)
            self.var_share.set(self.cfg["share_data"])
            self._update_share_state()
            d.destroy()
            self.root.deiconify()
            self.root.after(150, lambda: set_titlebar(self.root, self._theme_applied in DARK_THEMES, c["bg"], c["fg"]))
            self._start()

        ttk.Button(row, text=self.t("consent_agree"), style="Accent.TButton", command=agree).pack(side="right")
        ttk.Button(row, text=self.t("quit"), style="Panel.TButton", command=self.root.quit).pack(
            side="right", padx=(0, px(8)))
        d.update_idletasks()
        w, h = d.winfo_reqwidth(), d.winfo_reqheight()
        d.geometry(f"+{(d.winfo_screenwidth() - w) // 2}+{(d.winfo_screenheight() - h) // 3}")
        d.after(100, lambda: set_titlebar(d, self._theme_applied in DARK_THEMES, c["panel"], c["fg"]))
        d.focus_force()

    def _start(self):
        self.license.refresh(lambda: setattr(self, "_lic_dirty", True))
        self._log(f"Started. Work {fmt(self.work_s)}, idle reset {fmt(self.idle_s)}, break {fmt(self.break_s)}.")
        self.root.after(TICK_MS, self._tick)

    def run(self):
        if self.cfg["policy"] < POLICY_VERSION:
            self._ask_consent()
        else:
            self._start()
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            self.quit()
            try:
                self.root.destroy()
            except tk.TclError:
                pass


def main():
    p = argparse.ArgumentParser(description="Breyek - eye break assistant")
    p.add_argument("--work", type=int, default=20 * 60, help="work seconds (default 1200)")
    p.add_argument("--idle", type=int, default=5 * 60, help="idle-reset seconds (default 300)")
    p.add_argument("--break", dest="brk", type=int, default=60, help="break seconds (default 60)")
    p.add_argument("--test", action="store_true", help="demo mode: 20 s / 5 s / 10 s")
    p.add_argument("--minimized", action="store_true", help="start minimized (used by autostart)")
    a = p.parse_args()
    if a.test or DEMO:
        a.work, a.idle, a.brk = 20, 5, 10
    BreyekApp(a.work, a.idle, a.brk, a.minimized).run()


if __name__ == "__main__":
    main()

"""
Breyek - 20-20-20 style eye health enforcer (Windows)

Flow:
  WAITING  -> timer is full and not running. Starts on the first input.
  RUNNING  -> counts down WORK seconds. If there is no input for IDLE seconds,
              the timer resets and goes back to WAITING.
  LOCKED   -> dim fullscreen overlay on every monitor, all input blocked,
              big countdown + a rotating tip. After BREAK seconds -> WAITING.

UI:
  * Main window with the current status, a Settings box and a Language box.
  * Settings: (1) start with Windows, (2) small timer in the screen corner.
  * Languages: English, Lithuanian, Russian.
  * Closing the window (X) keeps the app running in the background (it just
    minimizes). Use the Quit button to exit completely.

Only the *fact* that input happened is recorded (no key logging).

Install:  pip install pynput
Run:      python breyek.py            (real: 20 min / 5 min idle / 1 min break)
          python breyek.py --test     (demo: 20 s / 5 s idle / 10 s break)
          python breyek.py --minimized  (start minimized, used by autostart)

Keep breyek.ico (and breyek-demo.ico for the demo) next to this script (window + taskbar icon).
Settings are saved in %APPDATA%\\Breyek\\config.json.
"Start with Windows" adds/removes a value in
HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run (no admin needed).

EMERGENCY EXIT while locked: hold Ctrl + Alt + Shift and press Q.
(Ctrl+Alt+Del can never be blocked by any app and also works.)
"""

import argparse
import ctypes
import json
import math
import os
import random
import sys
import time
import tkinter as tk
from ctypes import wintypes
from enum import Enum, auto
from tkinter import messagebox, ttk

from pynput import keyboard, mouse

try:
    import winreg
except ImportError:          # not on Windows
    winreg = None

# ----------------------------------------------------------------- settings


def _detect_demo():
    """Demo = the exe is named *demo*.exe (Breyek-Demo.exe) or --test was passed."""
    exe = sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
    return "demo" in os.path.basename(exe).lower() or "--test" in sys.argv


DEMO = _detect_demo()
APP_NAME = "Breyek-Demo" if DEMO else "Breyek"     # separate settings/startup entry per build
ICON_FILE = "breyek-demo.ico" if DEMO else "breyek.ico"
OVERLAY_ALPHA = 0.80          # 0 = invisible, 1 = solid black
TIP_ROTATE_SECONDS = 12
TICK_MS = 200

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
DEFAULTS = {"language": "en", "corner_timer": True}

# ---------------------------------------------------------------- languages
LANG_NAMES = {"en": "English", "lt": "Lietuvių", "ru": "Русский"}

STRINGS = {
    "en": {
        "window_title": "Breyek",
        "status_waiting": "Waiting for activity...",
        "status_running": "Next break in",
        "status_locked": "Break in progress",
        "settings": "Settings",
        "autostart": "Start with Windows",
        "corner_timer": "Show a small timer in the screen corner",
        "language": "Language",
        "hint_close": "Closing this window keeps the app running in the background.",
        "quit": "Quit",
        "break_title": "Time for an eye break",
        "error_title": "Error",
        "error_autostart": "Could not change the startup setting.",
    },
    "lt": {
        "window_title": "Breyek",
        "status_waiting": "Laukiama veiklos...",
        "status_running": "Kita pertrauka po",
        "status_locked": "Vyksta pertrauka",
        "settings": "Nustatymai",
        "autostart": "Paleisti kartu su „Windows“",
        "corner_timer": "Rodyti mažą laikmatį ekrano kampe",
        "language": "Kalba",
        "hint_close": "Uždarius langą programa toliau veikia fone.",
        "quit": "Išeiti",
        "break_title": "Laikas akių pertraukai",
        "error_title": "Klaida",
        "error_autostart": "Nepavyko pakeisti paleidimo nustatymo.",
    },
    "ru": {
        "window_title": "Breyek",
        "status_waiting": "Ожидание активности...",
        "status_running": "Следующий перерыв через",
        "status_locked": "Идёт перерыв",
        "settings": "Настройки",
        "autostart": "Запускать вместе с Windows",
        "corner_timer": "Показывать маленький таймер в углу экрана",
        "language": "Язык",
        "hint_close": "Если закрыть окно, приложение продолжит работать в фоне.",
        "quit": "Выход",
        "break_title": "Время дать глазам отдохнуть",
        "error_title": "Ошибка",
        "error_autostart": "Не удалось изменить настройку автозапуска.",
    },
}

TIPS = {
    "en": [
        "Look at something at least 6 m (20 ft) away.",
        "Slowly roll your eyes in a circle - 5 times each way.",
        "Blink slowly and fully 10 times to rewet your eyes.",
        "Stand up and walk around a bit.",
        "Go outside for a minute - natural light and distance are great for your eyes.",
        "Cover your eyes with warm palms for 20 seconds (palming).",
        "Look out of a window and focus on the farthest object you can see.",
        "Stretch your neck and shoulders, then drink some water.",
        "Focus on your thumb at arm's length, then on something far away. Repeat 5 times.",
    ],
    "lt": [
        "Pažiūrėkite į objektą bent 6 m atstumu.",
        "Lėtai sukite akis ratu – po 5 kartus į kiekvieną pusę.",
        "Lėtai ir visiškai primerkite akis 10 kartų, kad jos sudrėktų.",
        "Atsistokite ir šiek tiek pasivaikščiokite.",
        "Išeikite į lauką minutei – natūrali šviesa ir tolis akims labai naudingi.",
        "Šiltais delnais uždenkite akis 20 sekundžių.",
        "Pažiūrėkite pro langą ir sufokusuokite žvilgsnį į tolimiausią matomą objektą.",
        "Pasitempkite kaklą ir pečius, išgerkite vandens.",
        "Sufokusuokite žvilgsnį į nykštį ištiestoje rankoje, tada į tolimą objektą. Pakartokite 5 kartus.",
    ],
    "ru": [
        "Посмотрите на предмет, который находится не менее чем в 6 м от вас.",
        "Медленно вращайте глазами по кругу — по 5 раз в каждую сторону.",
        "Медленно и полностью моргните 10 раз, чтобы увлажнить глаза.",
        "Встаньте и немного пройдитесь.",
        "Выйдите на улицу на минуту — естественный свет и даль полезны для глаз.",
        "Закройте глаза тёплыми ладонями на 20 секунд.",
        "Посмотрите в окно и сфокусируйтесь на самом далёком предмете.",
        "Разомните шею и плечи, выпейте воды.",
        "Сфокусируйтесь на большом пальце вытянутой руки, затем на далёком предмете. Повторите 5 раз.",
    ],
}


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
    cfg["corner_timer"] = bool(cfg["corner_timer"])
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


def fmt(seconds):
    seconds = max(0, math.ceil(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


# ------------------------------------------------------------------- overlay
class Overlay:
    """One dimmed, borderless, always-on-top window covering one monitor."""

    def __init__(self, root, x, y, w, h, title_text):
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.configure(bg="black", cursor="none")
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", OVERLAY_ALPHA)

        box = tk.Frame(self.win, bg="black")
        box.place(relx=0.5, rely=0.46, anchor="center")

        self.title = tk.Label(
            box, text=title_text, fg="#9fb3c8", bg="black",
            font=("Segoe UI", -int(h * 0.04)),
        )
        self.timer = tk.Label(
            box, text="01:00", fg="white", bg="black",
            font=("Segoe UI", -int(h * 0.26), "bold"),
        )
        self.tip = tk.Label(
            box, text="", fg="#ffd479", bg="black",
            font=("Segoe UI", -int(h * 0.032)),
            wraplength=int(w * 0.6), justify="center",
        )
        self.title.pack()
        self.timer.pack(pady=int(h * 0.02))
        self.tip.pack(pady=int(h * 0.02))

    def update(self, timer_text, tip_text):
        self.timer.configure(text=timer_text)
        self.tip.configure(text=tip_text)

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


# ------------------------------------------------------------- corner timer
class CornerTimer:
    """Small always-on-top timer in the bottom-right corner. Clicks go through it."""

    MARGIN = 12

    def __init__(self, root, scale):
        self.root = root
        self.visible = True
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.configure(bg="#1b1b1b")
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.85)
        self.label = tk.Label(
            self.win, text="00:00", fg="white", bg="#1b1b1b",
            font=("Segoe UI", -int(22 * scale), "bold"),
            padx=int(12 * scale), pady=int(4 * scale),
        )
        self.label.pack()
        self._place()
        self._click_through()
        self.set_visible(False)

    def _place(self):
        self.win.update_idletasks()
        w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        left, top, right, bottom = get_work_area(self.root)
        self.win.geometry(f"+{right - w - self.MARGIN}+{bottom - h - self.MARGIN}")

    def _click_through(self):
        """Mouse clicks pass through the timer to whatever is below it."""
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetParent(self.win.winfo_id()) or self.win.winfo_id()
            style = user32.GetWindowLongW(hwnd, -20)             # GWL_EXSTYLE
            style |= 0x00080000 | 0x00000020 | 0x00000080 | 0x08000000
            # LAYERED | TRANSPARENT | TOOLWINDOW | NOACTIVATE
            user32.SetWindowLongW(hwnd, -20, style)
        except Exception:
            pass

    def set_visible(self, visible):
        if visible == self.visible:
            return
        self.visible = visible
        if visible:
            self._place()
            self.win.deiconify()
            self._click_through()
            self.win.attributes("-topmost", True)
        else:
            self.win.withdraw()

    def set_text(self, text, active):
        self.label.configure(text=text, fg="white" if active else "#8a8a8a")

    def close(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass


# ----------------------------------------------------------------------- app
class BreyekApp:
    def __init__(self, work_s, idle_s, break_s, start_minimized=False):
        self.work_s, self.idle_s, self.break_s = work_s, idle_s, break_s
        self.cfg = load_config()
        self.lang = self.cfg["language"]

        enable_dpi_awareness()
        set_taskbar_identity()
        self.root = tk.Tk()
        try:
            self.root.iconbitmap(resource_path(ICON_FILE))
        except tk.TclError:
            pass          # icon file missing: keep the default icon

        self.state = State.WAITING
        self.state_since = time.monotonic()
        self.last_input = 0.0          # written by listener threads (float write is atomic)
        self.run_start = 0.0
        self.lock_end = 0.0
        self.next_tip_at = 0.0
        self.current_tip = ""
        self.overlays = []
        self.blockers = []
        self.emergency = False
        self._quitting = False

        self._held = set()
        self.monitors = []     # activity comes from Windows itself (GetLastInputInfo), no hooks

        self._build_window()
        self.corner = CornerTimer(self.root, dpi_scale())
        self.apply_language()
        if start_minimized:
            self.root.after(100, self.root.iconify)

    # ------------------------------------------------- UI
    def t(self, key):
        return STRINGS[self.lang][key]

    def _build_window(self):
        r = self.root
        r.resizable(False, False)
        r.protocol("WM_DELETE_WINDOW", self._on_close)

        main = ttk.Frame(r, padding=16)
        main.pack(fill="both", expand=True)

        self.lbl_status = ttk.Label(main, font=("Segoe UI", 11), anchor="center")
        self.lbl_status.pack(fill="x")
        self.lbl_time = ttk.Label(main, font=("Segoe UI", 34, "bold"), anchor="center")
        self.lbl_time.pack(fill="x", pady=(0, 12))

        # --- settings
        self.box_settings = ttk.LabelFrame(main, padding=10)
        self.box_settings.pack(fill="x", pady=(0, 10))

        self.var_autostart = tk.BooleanVar(value=is_autostart_enabled())
        self.chk_autostart = ttk.Checkbutton(
            self.box_settings, variable=self.var_autostart, command=self._on_autostart
        )
        self.chk_autostart.pack(anchor="w")
        if DEMO:
            self.var_autostart.set(False)
            self.chk_autostart.state(["disabled"])      # a 20 s demo must never autostart

        self.var_corner = tk.BooleanVar(value=self.cfg["corner_timer"])
        self.chk_corner = ttk.Checkbutton(
            self.box_settings, variable=self.var_corner, command=self._on_corner
        )
        self.chk_corner.pack(anchor="w", pady=(6, 0))

        # --- language
        self.box_lang = ttk.LabelFrame(main, padding=10)
        self.box_lang.pack(fill="x", pady=(0, 10))

        self.var_lang = tk.StringVar(value=LANG_NAMES[self.lang])
        self.cmb_lang = ttk.Combobox(
            self.box_lang, textvariable=self.var_lang,
            values=list(LANG_NAMES.values()), state="readonly",
        )
        self.cmb_lang.pack(fill="x")
        self.cmb_lang.bind("<<ComboboxSelected>>", self._on_language)

        self.lbl_hint = ttk.Label(main, foreground="#666666", wraplength=320, justify="left")
        self.lbl_hint.pack(fill="x", pady=(0, 10))
        if DEMO:
            ttk.Label(
                main, foreground="#b00020", wraplength=320, justify="left",
                text=f"DEMO MODE: work {self.work_s} s, idle reset {self.idle_s} s, break {self.break_s} s",
            ).pack(fill="x", pady=(0, 10))

        self.btn_quit = ttk.Button(main, command=self.quit)
        self.btn_quit.pack(anchor="e")

    def apply_language(self):
        self.root.title(self.t("window_title") + (" (DEMO)" if DEMO else ""))
        self.box_settings.configure(text=self.t("settings"))
        self.chk_autostart.configure(text=self.t("autostart"))
        self.chk_corner.configure(text=self.t("corner_timer"))
        self.box_lang.configure(text=self.t("language"))
        self.lbl_hint.configure(text=self.t("hint_close"))
        self.btn_quit.configure(text=self.t("quit"))

    def _on_language(self, event=None):
        chosen = self.var_lang.get()
        for code, name in LANG_NAMES.items():
            if name == chosen:
                self.lang = code
                self.cfg["language"] = code
                save_config(self.cfg)
                break
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

    def _on_close(self):
        self.root.iconify()          # keep running in the background

    def _update_ui(self, now):
        if self.state is State.WAITING:
            status, secs, active = self.t("status_waiting"), self.work_s, False
        elif self.state is State.RUNNING:
            status, secs, active = self.t("status_running"), self.work_s - (now - self.run_start), True
        else:
            status, secs, active = self.t("status_locked"), self.lock_end - now, True

        self.lbl_status.configure(text=status)
        self.lbl_time.configure(text=fmt(secs))

        show_corner = self.cfg["corner_timer"] and self.state is not State.LOCKED
        self.corner.set_visible(show_corner)
        if show_corner:
            self.corner.set_text(fmt(secs), active)

    # ------------------------------------------------- input monitoring
    def _poll_input(self, now):
        """System-wide: any keyboard/mouse input in ANY app counts as activity."""
        idle = seconds_since_last_input()
        if idle is not None and self.state is not State.LOCKED:
            self.last_input = now - idle

    # ------------------------------------------------- input blocking
    CTRL = {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}
    ALT = {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr}
    SHIFT = {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r}

    def _block_press(self, key):
        # suppress=True swallows the event but we still get this callback,
        # which lets us watch for the emergency combo.
        self._held.add(key)
        if (
            getattr(key, "vk", None) == 0x51      # Q
            and self._held & self.CTRL
            and self._held & self.ALT
            and self._held & self.SHIFT
        ):
            self.emergency = True

    def _block_release(self, key):
        self._held.discard(key)

    def _start_blockers(self):
        self._held.clear()
        self.blockers = [
            mouse.Listener(suppress=True),
            keyboard.Listener(
                on_press=self._block_press,
                on_release=self._block_release,
                suppress=True,
            ),
        ]
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
        self._log(f"WAITING ({why}) - timer reset, waiting for input")

    def _to_running(self):
        self.state = State.RUNNING
        self.run_start = time.monotonic()
        self._log(f"RUNNING - {fmt(self.work_s)} until break")

    def _lock(self):
        self.state = State.LOCKED
        now = time.monotonic()
        self.lock_end = now + self.break_s
        self.next_tip_at = now
        self.corner.set_visible(False)
        title = self.t("break_title")
        self.overlays = [Overlay(self.root, *m, title) for m in get_monitors(self.root)]
        self._start_blockers()
        self._log("LOCKED - input blocked")

    def _unlock(self):
        self._stop_blockers()
        for o in self.overlays:
            o.close()
        self.overlays = []
        self._to_waiting("break finished")

    # ------------------------------------------------- main loop
    def _tick(self):
        now = time.monotonic()
        self._poll_input(now)

        if self.state is State.WAITING:
            if self.last_input > self.state_since:
                self._to_running()

        elif self.state is State.RUNNING:
            if now - self.last_input >= self.idle_s:
                self._to_waiting(f"no input for {fmt(self.idle_s)}")
            elif now - self.run_start >= self.work_s:
                self._lock()

        elif self.state is State.LOCKED:
            if self.emergency:
                self._log("EMERGENCY EXIT")
                self.quit()
                return

            remaining = math.ceil(self.lock_end - now)
            if remaining <= 0:
                self._unlock()
            else:
                if now >= self.next_tip_at:
                    self.current_tip = random.choice(TIPS[self.lang])
                    self.next_tip_at = now + TIP_ROTATE_SECONDS
                for o in self.overlays:
                    o.update(fmt(remaining), self.current_tip)
                    o.keep_on_top()

        self._update_ui(now)
        self.root.after(TICK_MS, self._tick)

    def quit(self):
        if self._quitting:
            return
        self._quitting = True
        self._stop_blockers()
        for listener in self.monitors:
            try:
                listener.stop()
            except Exception:
                pass
        for o in self.overlays:
            o.close()
        self.overlays = []
        self.corner.close()
        self.root.quit()

    def run(self):
        for listener in self.monitors:
            listener.start()
        self._log(
            f"Started. Work {fmt(self.work_s)}, idle reset {fmt(self.idle_s)}, "
            f"break {fmt(self.break_s)}. Ctrl+C in this window to quit."
        )
        self.root.after(TICK_MS, self._tick)
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
    p = argparse.ArgumentParser(description="Breyek - eye break reminder")
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

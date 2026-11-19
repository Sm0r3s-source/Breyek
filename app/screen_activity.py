"""
Screen movement detector for Breyek Lite (no data, no AI).

Once per second the screen is shrunk to a tiny grey picture (80x45 cells) and compared
with the previous one. If a clear part of the picture changed (video, animation, scrolling
page), the screen counts as "moving": somebody is probably watching it.

Privacy: the tiny picture lives only in memory, is replaced a second later, is never saved,
never leaves the program, and is far too small to read anything from. Nothing is recorded.

Limits: protected video (some Netflix / DRM players) is drawn black to screen capture and
cannot be seen. A looping animation or a live wallpaper counts as movement too.
"""

import ctypes
from collections import deque
from ctypes import wintypes

GRID_W, GRID_H = 160, 90
CELL_DIFF = 6             # grey level change (0-255) that makes a cell "changed"
MOVE_FRACTION = 0.01      # share of changed cells that counts as movement (a clock does not)
HISTORY = 5               # look at the last 5 samples ...
NEEDED = 3                # ... and call it moving if at least 3 of them showed movement
FAIL_LIMIT = 3            # consecutive capture failures before we report "unavailable"

SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 76, 77, 78, 79
SRCCOPY = 0x00CC0020
HALFTONE = 4
BI_RGB = 0
DIB_RGB_COLORS = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def changed_fraction(a, b, cell_diff=CELL_DIFF):
    """Share of cells whose grey level differs by more than cell_diff."""
    if not a or not b or len(a) != len(b):
        return 0.0
    n = sum(1 for x, y in zip(a, b) if abs(x - y) > cell_diff)
    return n / len(a)


def grab_gray():
    """Whole desktop (all monitors) as GRID_W*GRID_H grey values 0-255, or None on failure."""
    try:
        user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
        user32.GetDC.restype = wintypes.HDC
        user32.GetDC.argtypes = [wintypes.HWND]
        user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        gdi32.CreateCompatibleDC.restype = wintypes.HDC
        gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
        gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
        gdi32.SelectObject.restype = wintypes.HGDIOBJ
        gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        gdi32.SetStretchBltMode.argtypes = [wintypes.HDC, ctypes.c_int]
        gdi32.StretchBlt.argtypes = [
            wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.DWORD,
        ]
        gdi32.GetDIBits.argtypes = [
            wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
            ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT,
        ]
        gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        gdi32.DeleteDC.argtypes = [wintypes.HDC]

        x, y = user32.GetSystemMetrics(SM_XVIRTUALSCREEN), user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        w, h = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN), user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        if w <= 0 or h <= 0:
            return None

        screen_dc = user32.GetDC(None)
        if not screen_dc:
            return None
        mem_dc = bmp = old = None
        try:
            mem_dc = gdi32.CreateCompatibleDC(screen_dc)
            bmp = gdi32.CreateCompatibleBitmap(screen_dc, GRID_W, GRID_H)
            if not mem_dc or not bmp:
                return None
            old = gdi32.SelectObject(mem_dc, bmp)
            gdi32.SetStretchBltMode(mem_dc, HALFTONE)
            if not gdi32.StretchBlt(mem_dc, 0, 0, GRID_W, GRID_H, screen_dc, x, y, w, h, SRCCOPY):
                return None
            gdi32.SelectObject(mem_dc, old)          # GetDIBits needs the bitmap NOT selected in a DC
            old = None
            header = BITMAPINFOHEADER()
            header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            header.biWidth, header.biHeight = GRID_W, -GRID_H        # negative = top-down rows
            header.biPlanes, header.biBitCount, header.biCompression = 1, 32, BI_RGB
            buf = ctypes.create_string_buffer(GRID_W * GRID_H * 4)
            lines = gdi32.GetDIBits(screen_dc, bmp, 0, GRID_H, buf, ctypes.byref(header), DIB_RGB_COLORS)
            if lines != GRID_H:
                return None
            raw = buf.raw                                              # B, G, R, unused per pixel
            return [(raw[i + 2] * 3 + raw[i + 1] * 6 + raw[i]) // 10 for i in range(0, len(raw), 4)]
        finally:
            if old:
                gdi32.SelectObject(mem_dc, old)
            if bmp:
                gdi32.DeleteObject(bmp)
            if mem_dc:
                gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(None, screen_dc)
    except Exception:
        return None


class ScreenWatcher:
    """Call sample() about once per second; read .moving."""

    def __init__(self, grab=grab_gray):
        self._grab = grab
        self.reset()

    def reset(self):
        """Forget the last picture (use after the break overlay was shown)."""
        self._prev = None
        self._hist = deque(maxlen=HISTORY)
        self.failures = 0
        self.last_fraction = 0.0

    def sample(self):
        frame = self._grab()
        if frame is None:
            self.failures += 1
            self._prev = None
            self._hist.append(False)
            return
        self.failures = 0
        if self._prev is not None:
            self.last_fraction = changed_fraction(self._prev, frame)
            self._hist.append(self.last_fraction >= MOVE_FRACTION)
        self._prev = frame

    @property
    def moving(self):
        return sum(self._hist) >= NEEDED

    @property
    def unavailable(self):
        return self.failures >= FAIL_LIMIT


if __name__ == "__main__":
    # Diagnostic:  py screen_activity.py   (play a video, watch the numbers, Ctrl+C to stop)
    import time
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    watcher = ScreenWatcher()
    print("Screen check. 'changed' = share of the screen that changed in the last second.")
    print("Video should show roughly 1-50 %, a still screen about 0 %.  Ctrl+C to stop.")
    while True:
        frame = watcher._grab()
        if frame is None:
            print("CAPTURE FAILED (grab_gray returned None)")
        else:
            watcher._grab = lambda f=frame: f
            watcher.sample()
            watcher._grab = grab_gray
            avg = sum(frame) / len(frame)
            print(f"average brightness {avg:5.1f}   changed {watcher.last_fraction * 100:5.2f} %   "
                  f"moving: {watcher.moving}")
        time.sleep(1)

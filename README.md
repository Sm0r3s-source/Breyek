# Breyek

An on-device eye-health app for Windows. Breyek watches how long you have been actively using the computer and forces a short break every 20 minutes, in the spirit of the 20-20-20 rule.

## How it works

1. The 20-minute timer starts on your first keyboard or mouse input and only counts while you are active.
2. If there is no input for 5 minutes, the timer resets and waits until you start working again.
3. After 20 minutes of activity, a dimmed full-screen overlay covers every monitor, all input is blocked, and a 1-minute countdown is shown with a tip (eye exercises, walking, going outside).
4. When the minute ends, the computer unlocks and the cycle starts again.

Only the *fact* that input happened is used (Windows' own idle timer). Keystrokes are never recorded.

## Features

- Settings: start with Windows, optional small timer in the screen corner
- Languages: English, Lithuanian (Lietuvių), Russian (Русский)
- Break screen with rotating eye-health tips
- Emergency exit during a break: hold `Ctrl + Alt + Shift` and press `Q` (`Ctrl + Alt + Del` always works too)

## Run from source

Requires Windows and Python 3.10+.

```
py -m pip install -r requirements.txt
py breyek.py          # full version: 20 min / 5 min idle / 1 min break
py breyek.py --test   # demo version: 20 s / 5 s idle / 10 s break
```

Keep `breyek.ico` and `breyek-demo.ico` next to `breyek.py`.

## Build the .exe files

Double-click `build.bat`. It creates two files in the `dist` folder:

- `Breyek.exe` - full version
- `Breyek-Demo.exe` - demo version (short timings, start-with-Windows disabled)

Prebuilt files are available on the Releases page. Because Breyek blocks input during a break, antivirus software may show a warning for the unsigned `.exe`.

## Known limitations

- Windows only.
- Any mouse movement counts as activity, because Windows does not say what kind of input it was.
- Watching a video or reading without touching the mouse or keyboard counts as idle.

## Team

Add your team names here.

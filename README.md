# Breyek

Breyek is a free Windows app that reminds you to rest your eyes. After 20 minutes of screen time it gives you a 1-minute break and blocks the keyboard and mouse until it ends. It checks *when* you type, use the mouse or the screen changes, never *what* you type or see.

- 40 languages, light and dark theme, warm eye filter
- Pauses videos and music during the break
- Weekly statistics kept on your computer
- Optional, opt-in anonymous usage data ([privacy policy](https://breyek-api.breyek-api.workers.dev/privacy))

Emergency exit during a break: **Ctrl + Alt + Shift + Q**

## Download

Get the latest `Breyek-2.0.exe` from [Releases](../../releases).

## Build from source

Windows, Python 3.10 or newer:

```
cd app
build.bat
```

The programs appear in `app\dist\`.

## Repository

- `app/` – the Windows app (Python, tkinter)
- `api/` – the Cloudflare Worker that receives opt-in usage reports and serves the privacy policy (see `api/README.txt`)

## Contact

Bugs, support and partnerships: breyek@protonmail.com

Made by a student team at Lietuvos inžinerijos kolegija.

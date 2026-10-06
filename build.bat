@echo off
setlocal
cd /d "%~dp0"

rem Use the "py" launcher (your real Python); fall back to "python" if there is no launcher.
set "PY=py"
where py >nul 2>nul || set "PY=python"
echo Using: %PY%
%PY% --version

echo.
echo === Installing build tools ===
%PY% -m pip install --upgrade pyinstaller pynput || goto :error

echo.
echo === Building FULL version: Breyek.exe (20 min / 5 min / 1 min) ===
%PY% -m PyInstaller --noconfirm --clean --onefile --noconsole --name Breyek ^
  --icon breyek.ico --add-data "breyek.ico;." ^
  --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 ^
  breyek.py || goto :error

echo.
echo === Building DEMO version: Breyek-Demo.exe (20 s / 5 s / 10 s) ===
%PY% -m PyInstaller --noconfirm --onefile --noconsole --name Breyek-Demo ^
  --icon breyek-demo.ico --add-data "breyek-demo.ico;." ^
  --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 ^
  breyek.py || goto :error

echo.
echo Done. Your files are in the "dist" folder:
echo    dist\Breyek.exe        (full version)
echo    dist\Breyek-Demo.exe   (demo version)
pause
exit /b 0

:error
echo.
echo Build failed. Scroll up to see the error.
pause
exit /b 1

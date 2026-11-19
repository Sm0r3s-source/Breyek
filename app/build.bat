@echo off
setlocal
cd /d "%~dp0"

set "PY=py"
where py >nul 2>nul || set "PY=python"
echo Using: %PY%
%PY% --version

echo.
echo === Installing build tools ===
%PY% -m pip install --upgrade pyinstaller -r requirements.txt || goto :error

echo.
echo === Building Breyek.exe (full: 20 min / 5 min / 1 min) ===
call :build Breyek breyek.ico || goto :error

echo.
echo === Building Breyek-Demo.exe (demo: 20 s / 5 s / 10 s) ===
call :build Breyek-Demo breyek-demo.ico || goto :error

echo.
echo Done. Your files are in the "dist" folder:
echo    dist\Breyek.exe
echo    dist\Breyek-Demo.exe
pause
exit /b 0

:build
%PY% -m PyInstaller --noconfirm --onefile --noconsole --name %~1 --icon %~2 --add-data "%~2;." --add-data "lang;lang" --add-data "sponsor_lik_light.png;." --add-data "sponsor_lik_dark.png;." --hidden-import PIL._tkinter_finder --collect-submodules winrt --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 breyek.py
exit /b %errorlevel%

:error
echo.
echo Build failed. Scroll up to see the error.
pause
exit /b 1

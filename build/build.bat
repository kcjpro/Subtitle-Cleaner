@echo off
setlocal ENABLEDELAYEDEXPANSION
cd /d "%~dp0"

echo === Subtitle Cleaner build (slim portable, mpv playback) ===
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python is not on PATH. Install Python 3.10-3.12 first.
    exit /b 1
)

REM Show which Python we're building with - 3.13/3.14 cause native-lib breakage.
echo Build Python:
python -c "import sys; print('  ' + sys.version)"
python -c "import sys; ver=sys.version_info; sys.exit(0 if ver < (3,13) else 1)" >nul 2>nul
if errorlevel 1 (
    echo.
    echo WARNING: Python 3.13+ is bleeding-edge. Many wheels ^(especially
    echo          native ones for PySide6 / faster-whisper^) lag the release
    echo          by months. If the build fails or the .exe won't launch,
    echo          install Python 3.12 from https://www.python.org/ and try
    echo          again from a fresh venv:
    echo              py -3.12 -m venv .build-env
    echo              .build-env\Scripts\activate
    echo              build\build.bat
    echo.
)

echo Installing/updating build + runtime dependencies...
python -m pip install --upgrade pip >nul
python -m pip install -r "..\requirements.txt"
if errorlevel 1 goto :err
python -m pip install pyinstaller
if errorlevel 1 goto :err

echo.
echo NOTE: This build is the slim default. It bundles libmpv-2.dll +
echo       ffmpeg/ffprobe so playback and subtitle scanning work out of
echo       the box. It does NOT bundle the heavy optional features
echo       ^(faster-whisper, NudeNet, cloud LLM SDKs^); users opt in to
echo       those from the in-app Settings -^> Optional Features tab,
echo       or run from source after installing:
echo           pip install -r requirements-whisper.txt
echo           pip install -r requirements-llm.txt
echo           pip install -r requirements-visual.txt
echo.

set "MISSING="
if exist "bin\libmpv-2.dll" (
    echo Bundling libmpv-2.dll from build\bin
) else (
    set "MISSING=1"
    echo NOTE: build\bin\libmpv-2.dll not found.
    echo       Without it, video playback will not work.
    echo       The MAKE_INSTALLER.bat driver downloads this for you.
)
if exist "bin\ffmpeg.exe" (
    echo Bundling ffmpeg.exe + ffprobe.exe from build\bin
) else (
    set "MISSING=1"
    echo NOTE: build\bin\ffmpeg.exe not found.
    echo       Drop ffmpeg.exe and ffprobe.exe in there to bundle them.
    echo       Without them, the built app falls back to your system ffmpeg.
)
echo.

echo Running PyInstaller (full log: build\pyinstaller.log)...
python -m PyInstaller --noconfirm --clean --log-level=WARN SubtitleCleaner.spec > pyinstaller.log 2>&1
set "PYI_RC=!ERRORLEVEL!"
echo PyInstaller exit code: !PYI_RC!

REM Always show the tail of the log so failures are visible.
echo.
echo --- last 60 lines of build\pyinstaller.log ---
powershell -NoProfile -Command "Get-Content -Path 'pyinstaller.log' -Tail 60"
echo --- end of log tail ---
echo.

if not "!PYI_RC!"=="0" goto :err

REM Sanity check: did PyInstaller actually produce the exe?
if not exist "dist\SubtitleCleaner\SubtitleCleaner.exe" (
    echo.
    echo ERROR: PyInstaller exited 0 but did not produce SubtitleCleaner.exe.
    echo Check build\pyinstaller.log for details.
    echo Folder contents of build\dist\:
    if exist "dist" (dir /s /b "dist") else (echo   ^(dist folder does not exist^))
    goto :err
)

echo.
echo ============================================================
echo Build complete.
echo Open: dist\SubtitleCleaner\SubtitleCleaner.exe
echo Zip the SubtitleCleaner folder to share the portable app.
echo ============================================================
exit /b 0

:err
echo.
echo Build failed. See output above and build\pyinstaller.log for details.
pause
exit /b 1

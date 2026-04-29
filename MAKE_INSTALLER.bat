@echo off
setlocal ENABLEDELAYEDEXPANSION
cd /d "%~dp0"

echo ============================================================
echo  Subtitle Cleaner - one-click installer + portable build
echo ============================================================
echo.

REM ---------------------------------------------------------------
REM 1. Verify Python
REM ---------------------------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python is not on PATH.
    echo Install Python 3.10 or newer from https://www.python.org/
    echo and re-run this script.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------
REM 2. Locate Inno Setup compiler (ISCC.exe)
REM ---------------------------------------------------------------
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe"      set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe"

if "!ISCC!"=="" (
    echo ERROR: Inno Setup not found.
    echo This is a free, ~5 MB download required to package the installer.
    echo Get it from: https://jrsoftware.org/isdl.php
    echo Install it ^(default options are fine^), then re-run this script.
    pause
    exit /b 1
)
echo Found Inno Setup compiler:
echo     "!ISCC!"
echo.

REM ---------------------------------------------------------------
REM 3. WIPE previous build artifacts so the new exclude rules take effect.
REM     (PyInstaller's --clean only clears its work cache, not dist\ )
REM ---------------------------------------------------------------
echo Step 1/6 - Cleaning previous build output...
if exist "build\dist"  rmdir /s /q "build\dist"
if exist "build\build" rmdir /s /q "build\build"
if exist "installer\Output" rmdir /s /q "installer\Output"

REM ---------------------------------------------------------------
REM 4. Download libmpv-2.dll + ffmpeg into installer\deps\ (skips if present)
REM ---------------------------------------------------------------
echo.
echo Step 2/6 - Preparing dependencies (libmpv-2.dll, ffmpeg)...
powershell -NoProfile -ExecutionPolicy Bypass -File "installer\download_deps.ps1"
if errorlevel 1 (
    echo.
    echo ERROR: dependency download failed.
    echo You can manually drop these files into installer\deps\ and re-run:
    echo     libmpv-2.dll       ^(from https://sourceforge.net/projects/mpv-player-windows/files/libmpv/^)
    echo     ffmpeg.exe         ^(from https://www.gyan.dev/ffmpeg/builds/^)
    echo     ffprobe.exe
    pause
    exit /b 1
)

REM ---------------------------------------------------------------
REM 5. Mirror libmpv-2.dll + ffmpeg into build\bin so the PyInstaller spec bundles them
REM ---------------------------------------------------------------
if not exist "build\bin" mkdir "build\bin"
copy /Y "installer\deps\ffmpeg.exe"     "build\bin\ffmpeg.exe"     >nul
copy /Y "installer\deps\ffprobe.exe"    "build\bin\ffprobe.exe"    >nul
copy /Y "installer\deps\libmpv-2.dll"   "build\bin\libmpv-2.dll"   >nul

REM ---------------------------------------------------------------
REM 6. Build the PyInstaller bundle
REM ---------------------------------------------------------------
echo.
echo Step 3/6 - Building application bundle (PyInstaller)...
call "build\build.bat"
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

if not exist "build\dist\SubtitleCleaner\SubtitleCleaner.exe" (
    echo ERROR: build did not produce build\dist\SubtitleCleaner\SubtitleCleaner.exe
    pause
    exit /b 1
)

REM ---------------------------------------------------------------
REM 7. Compile the installer
REM ---------------------------------------------------------------
echo.
echo Step 4/6 - Compiling Inno Setup installer...
"!ISCC!" "installer\SubtitleCleaner.iss"
if errorlevel 1 (
    echo Inno Setup compilation failed.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------
REM 8. Zip the portable bundle for distribution
REM ---------------------------------------------------------------
echo.
echo Step 5/6 - Zipping portable bundle...
if not exist "installer\Output" mkdir "installer\Output"
set "PORTABLE_ZIP=installer\Output\SubtitleCleaner-Portable.zip"
if exist "!PORTABLE_ZIP!" del /Q "!PORTABLE_ZIP!"

powershell -NoProfile -Command ^
  "Compress-Archive -Path 'build\dist\SubtitleCleaner\*' -DestinationPath '!PORTABLE_ZIP!' -CompressionLevel Optimal"
if errorlevel 1 (
    echo Portable zip creation failed.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------
REM 9. Done
REM ---------------------------------------------------------------
echo.
echo Step 6/6 - Done.
echo.
echo ============================================================
echo  SUCCESS
echo  Installer: installer\Output\SubtitleCleaner-Setup.exe
echo  Portable:  installer\Output\SubtitleCleaner-Portable.zip
echo.
echo  Both bundle libmpv-2.dll + ffmpeg, so end users do not need
echo  to install VLC, mpv, or anything else separately.
echo ============================================================
echo.
pause
exit /b 0

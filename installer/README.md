# Installer

One-click Windows installer for Subtitle Cleaner. Wraps the slim
PyInstaller bundle in an [Inno Setup](https://jrsoftware.org/isinfo.php)
installer that:

- Copies the app to `C:\Program Files\SubtitleCleaner\`
- Creates Start Menu and (optional) Desktop shortcuts
- Bundles `ffmpeg.exe` + `ffprobe.exe` next to the app
- Detects whether VLC is installed; if not, runs the bundled VLC installer
  silently so the end user truly clicks once

## End-user experience

Double-click `SubtitleCleaner-Setup.exe`. A wizard appears; click Next a
couple of times. If VLC isn't installed, the installer silently installs
VLC after copying our files, then offers to launch the app. Done.

## To produce the installer (developer side)

One-time setup:

1. Install [Inno Setup](https://jrsoftware.org/isdl.php) (free, ~5 MB).
   Default options are fine.
2. Make sure Python 3.10+ is on PATH.

Then, from the project root, double-click or run:

```bat
MAKE_INSTALLER.bat
```

That single command will:

1. Auto-download the latest VLC installer + ffmpeg into `installer\deps\`
   (skipped if already present).
2. Mirror `ffmpeg.exe` / `ffprobe.exe` into `build\bin\` so PyInstaller
   bundles them.
3. Run `build\build.bat` to produce the slim PyInstaller bundle in
   `build\dist\SubtitleCleaner\`.
4. Run Inno Setup against `installer\SubtitleCleaner.iss`.
5. Output: `installer\Output\SubtitleCleaner-Setup.exe`. ~120 MB. One file
   to hand to anyone.

## Folder layout

```
installer\
    SubtitleCleaner.iss     Inno Setup script (with VLC detection logic)
    download_deps.ps1       PowerShell helper to fetch VLC + ffmpeg
    deps\                   Auto-populated with vlc-installer.exe, ffmpeg.exe, ffprobe.exe
    Output\                 Generated; SubtitleCleaner-Setup.exe lives here
```

## Manual deps (no internet on build machine)

Drop these into `installer\deps\` yourself before running MAKE_INSTALLER.bat:

- `vlc-installer.exe` — any 64-bit VLC installer from
  <https://www.videolan.org/vlc/download-windows.html>
- `ffmpeg.exe` and `ffprobe.exe` — from any 64-bit ffmpeg build, e.g.
  <https://www.gyan.dev/ffmpeg/builds/> (release essentials zip)

The download script skips anything that's already there.

## Customizing

- **App version:** edit `#define MyAppVersion` near the top of
  `SubtitleCleaner.iss`.
- **Install location:** change `DefaultDirName` in `[Setup]`.
- **Icon:** add an `.ico` file and set `SetupIconFile` in `[Setup]`, plus
  `icon=` in `build\SubtitleCleaner.spec` for the .exe itself.
- **Skip the VLC install:** delete the `[Code]` block at the bottom of the
  .iss and the `dontcopy` entry under `[Files]`.

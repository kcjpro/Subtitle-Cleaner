# Building the Windows .exe

A one-folder portable build via [PyInstaller](https://pyinstaller.org/).
The result is a `SubtitleCleaner` folder containing `SubtitleCleaner.exe`
plus its supporting files. Zip it to share. Bundle weighs ~120-180 MB
(varies a bit with which libmpv build you grab).

## What this build includes (and what it doesn't)

This is the **slim portable** build. It ships:

- `SubtitleCleaner.exe`                 (the app)
- `bin/libmpv-2.dll`                    (video playback engine)
- `bin/ffmpeg.exe` + `bin/ffprobe.exe`  (audio + subtitle extraction)
- `data/wordlists/*.txt`                (editable in place)

It scans:

- Sidecar subtitles (`movie.srt` / `movie.vtt` next to the video).
- Subtitle tracks embedded in MKV/MP4 files, extracted via ffmpeg.

It does **not** bundle the heavy optional features:

- `faster-whisper` audio transcription (~350 MB native deps)
- `nudenet` visual nudity detection (~200 MB onnxruntime + weights)
- Cloud LLM SDKs (`google-generativeai`, `groq`)

Users opt in to those at runtime from the in-app **Settings -> Optional
Features** tab, which pip-installs them into a per-user environment
without rebuilding the app. Or, run the app from Python source after:

```bat
pip install -r requirements-whisper.txt
pip install -r requirements-llm.txt
pip install -r requirements-visual.txt
python main.py
```

The PyInstaller spec actively *excludes* these heavy packages even if
they happen to be installed in your build env, so the bundle stays slim
regardless.

## Prerequisites

- Windows 10 / 11
- Python 3.10-3.12 on PATH (3.12 recommended; PySide6 wheels for 3.13/3.14
  occasionally lag the release).
- [Inno Setup 6](https://jrsoftware.org/isdl.php) (free, ~5 MB) if you want
  the `SubtitleCleaner-Setup.exe` installer too. The portable build does
  not need Inno Setup.

End users do **not** need anything pre-installed (no VLC, no mpv, no
Python). The bundle is self-contained.

## One-click build (recommended)

From the project root, double-click or run:

```bat
MAKE_INSTALLER.bat
```

This will:

1. Download `libmpv-2.dll`, `ffmpeg.exe`, `ffprobe.exe` into
   `installer\deps\` (skipped on subsequent runs).
2. Mirror them into `build\bin\` so the spec bundles them.
3. Run PyInstaller to produce `build\dist\SubtitleCleaner\`.
4. Compile the Inno Setup installer.
5. Zip the portable bundle.

Outputs land in `installer\Output\`:

- `SubtitleCleaner-Setup.exe`     (one-click installer)
- `SubtitleCleaner-Portable.zip`  (unzip + double-click)

## Just the portable build (no installer)

Drop `libmpv-2.dll`, `ffmpeg.exe`, and `ffprobe.exe` into `build\bin\`,
then run:

```bat
build\build.bat
```

(or `python build\build_exe.py` if you prefer).

Final output:

```
build\dist\SubtitleCleaner\
    SubtitleCleaner.exe
    _internal\...                 (PyInstaller's bundled libs - leave alone)
    bin\libmpv-2.dll              (video playback)
    bin\ffmpeg.exe                (subtitle / audio extraction)
    bin\ffprobe.exe
    data\wordlists\*.txt          (editable in place)
    data\profiles\                (auto-populated as you scan videos)
```

Zip the `SubtitleCleaner` folder to ship a portable build.

## Customising the exe

- **Icon:** put an `.ico` file somewhere and set `icon=` in
  [SubtitleCleaner.spec](SubtitleCleaner.spec) (`exe = EXE(... icon="path/to/icon.ico")`).
- **Console window for debugging:** flip `console=False` to `console=True`
  in the spec, rebuild. Stdout/stderr (including any Python tracebacks)
  will then show in a console.

## Troubleshooting

**"Failed to execute script main"** on launch — usually a missing hidden
import. Set `console=True` in the spec, rebuild, run from a terminal, and
read the traceback. Add the missing module name to the `hiddenimports`
list near the bottom of the spec.

**"python-mpv could not be loaded" / black video pane** — `libmpv-2.dll`
isn't next to the exe under `bin\`. Drop it there and re-launch. The
MAKE_INSTALLER.bat workflow handles this automatically.

**Lots of "missing module" warnings during build** — those are PyInstaller
diagnostic noise, not errors. Most are platform-specific modules
(`pwd`, `grp`, `fcntl` from POSIX) or optional deps in transitively imported
libraries (numpy / torch / transformers / etc.). The slim spec excludes the
heavyweights so the bundle stays small. As long as the build finishes and
the .exe launches, the warnings can be ignored.

**Bundle is much bigger than expected** — you probably have
`faster-whisper` or another large package installed in the env you built
from, and PyInstaller is pulling something in despite the excludes.
Uninstall the heavy packages from your build env (or build inside a fresh
virtualenv) and rebuild.

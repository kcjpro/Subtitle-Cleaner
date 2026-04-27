# Building the Windows .exe

A one-folder portable build via [PyInstaller](https://pyinstaller.org/).
The result is a `SubtitleCleaner` folder containing `SubtitleCleaner.exe`
plus its supporting files. Zip it to share. Bundle weighs ~50–80 MB.

## What this build includes (and what it doesn't)

This is a **slim, subtitle-only** build. It scans:

- Sidecar subtitles (`movie.srt` / `movie.vtt` next to the video).
- Subtitle tracks embedded in MKV files, extracted via ffmpeg.

It does **not** include `faster-whisper` audio transcription. That stack
(`ctranslate2` + `onnxruntime`) adds ~350 MB and a lot of fragile native
dependencies that don't bundle cleanly. The PyInstaller spec actively
*excludes* it even if you happen to have it installed in your env.

If you need transcription (i.e. for videos with no subtitle track at all),
run the app from Python source instead:

```bat
pip install -r requirements-whisper.txt
python main.py
```

In practice, virtually all movies and TV episodes you'd run this against
already have an embedded or sidecar subtitle track, so the slim build covers
the common case.

## Prerequisites

- Windows 10 / 11
- Python 3.10+ on PATH
- VLC media player installed on the **target** machine — `python-vlc` binds
  to it at runtime. Don't try to bundle VLC; install it as a separate app
  from <https://www.videolan.org/>.

If your dev env happens to have `faster-whisper` / `ctranslate2` /
`onnxruntime` installed, the spec excludes them, but uninstalling them
before building will speed up PyInstaller's analysis pass and quiet the
"missing modules" noise:

```bat
pip uninstall -y faster-whisper ctranslate2 onnxruntime
```

## Optional: bundle ffmpeg

If you drop `ffmpeg.exe` and `ffprobe.exe` into `build\bin\`, the build
script will copy them next to the .exe so the app works on machines that
don't have ffmpeg installed. See `build\bin\README.txt` for download links.

If you skip this, the built app will look for ffmpeg/ffprobe on the user's
PATH at runtime instead.

## Build

From the repo root, double-click or run:

```bat
build\build.bat
```

Or, if you prefer Python:

```bat
python build\build_exe.py
```

The build script will:

1. Install/update `pip`, the slim runtime requirements, and PyInstaller.
2. Run `pyinstaller --noconfirm --clean SubtitleCleaner.spec`.
3. Make sure `dist\SubtitleCleaner\data\profiles\` exists.

Final output:

```
build\dist\SubtitleCleaner\
    SubtitleCleaner.exe
    _internal\...                 (PyInstaller's bundled libs — leave alone)
    bin\ffmpeg.exe                (only if you bundled it)
    bin\ffprobe.exe
    data\wordlists\*.txt          (editable in place)
    data\profiles\                (auto-populated as you scan videos)
```

Zip the `SubtitleCleaner` folder to ship a portable build.

## Customising the exe

- **Icon:** put an `.ico` file somewhere and set `icon=` in
  `SubtitleCleaner.spec` (`exe = EXE(... icon="path/to/icon.ico")`).
- **Console window for debugging:** flip `console=False` to `console=True`
  in the spec, rebuild. Stdout/stderr (including any Python tracebacks)
  will then show in a console.

## Troubleshooting

**"Failed to execute script main"** on launch — usually a missing hidden
import. Set `console=True` in the spec, rebuild, run from a terminal, and
read the traceback. Add the missing module name to the `hiddenimports`
list near the bottom of the spec.

**VLC errors / no video shown** — VLC isn't installed on the target
machine, or it's a 32-bit / 64-bit mismatch with the Python that built the
exe. The Python interpreter you build with and the installed VLC must be
the same architecture (both 64-bit is the norm).

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

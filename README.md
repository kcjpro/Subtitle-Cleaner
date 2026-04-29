# Subtitle Cleaner

A standalone desktop video player that scans video files for profanity,
blasphemy, sexually explicit language, and on-screen nudity, then mutes
or skips flagged sections during playback.

Inspired by ClearPlay. Designed for personal/family use.

## Features

- Plays MP4, MKV, AVI, MOV, and other formats supported by mpv.
- Pre-scans every video using a stack of detection sources, all of which
  can be combined:
  - **Embedded subtitles** in MKV/MP4 files (extracted via ffmpeg).
  - **Sidecar subtitle files** (`movie.srt`, `movie.vtt`) next to the video.
  - **Audio transcription** with [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
    for word-level timestamps when no subtitles are available.
  - **LLM context analysis** (Ollama / Gemini / Groq) to flag implied
    sexual situations, innuendo, and disturbing dialogue beyond simple
    wordlist matches.
  - **Visual nudity detection** via [NudeNet](https://github.com/notAI-tech/NudeNet)
    on sampled frames.
- Categorizes flagged words into **blasphemy**, **vulgarity**, **sexual**,
  and **slurs** using editable wordlists in `data/wordlists/`.
- **Review dialog** with category summary cards, search/filter, type
  badges (audio vs visual), and confidence indicators.
- Saves a **filter profile** per video in `data/profiles/` so you only
  review once.
- During playback, mpv handles the video; the app watches the playback
  position and **mutes** or **skips** the chosen ranges automatically.
- Modern dark UI (qtawesome icons, hand-rolled QSS) with a frame-accurate
  scrubber.

## Quick start (click-to-run)

Grab the prebuilt artifacts from
[GitHub Releases](https://github.com/kcjpro/Subtitle-Cleaner/releases) or
build them yourself (below).

| Platform | Format | Size |
|----------|--------|------|
| Windows  | `SubtitleCleaner-Setup.exe`        | ~120 MB |
| Windows  | `SubtitleCleaner-Portable.zip`     | ~165 MB |
| macOS    | `SubtitleCleaner.dmg`              | similar |
| macOS    | `SubtitleCleaner-mac.zip` (portable .app) | similar |

The click-to-run app ships with `libmpv` + `ffmpeg` + `ffprobe` bundled,
so end users do **not** need to install VLC, mpv, ffmpeg, or anything
else separately.

The slim build covers subtitle scanning + playback. The heavier optional
features (Whisper, NudeNet, cloud LLM SDKs) are installed on-demand from
**Settings -> Optional Features** in the running app — no rebuild
needed.

## Run from source

For development / faster iteration:

```bash
pip install -r requirements.txt
python main.py
```

You'll need:

- Python 3.10-3.12 (3.12 recommended)
- mpv / libmpv on the system:
  - **Windows:** drop `libmpv-2.dll` into `bin/` next to `main.py`
  - **macOS:** `brew install mpv ffmpeg`
  - **Linux:** `apt install libmpv2 ffmpeg`
- ffmpeg + ffprobe on PATH (or in `bin/` next to `main.py`)

Optional features:

```bash
pip install -r requirements-whisper.txt   # faster-whisper transcription
pip install -r requirements-llm.txt       # Gemini + Groq SDKs
pip install -r requirements-visual.txt    # NudeNet + onnxruntime
```

## Build the installers locally

### Windows

```bat
MAKE_INSTALLER.bat
```

Downloads `libmpv-2.dll` + `ffmpeg.exe` + `ffprobe.exe` automatically,
runs PyInstaller, compiles the Inno Setup installer, and zips the
portable bundle. Outputs land in `installer\Output\`.

One-time prerequisites: Python 3.10-3.12,
[Inno Setup](https://jrsoftware.org/isdl.php) (free, ~5 MB), and
[7-Zip](https://www.7-zip.org/) (free, ~2 MB; Inno Setup's installer
ships it). Full walkthrough: [build/README.md](build/README.md).

### macOS

```bash
bash scripts/setup_mac.sh           # one-time: brew, python@3.12, mpv, ffmpeg, ...
bash MAKE_INSTALLER.command          # full build
```

`setup_mac.sh` is idempotent and only installs what's missing. Full
walkthrough: [docs/MAC_BUILD.md](docs/MAC_BUILD.md).

### GitHub Actions (cloud builds)

Push to a GitHub repo and the bundled
[`.github/workflows/build-installer.yml`](.github/workflows/build-installer.yml)
spins up a clean Windows runner, builds, and uploads
`SubtitleCleaner-Setup.exe` and `SubtitleCleaner-Portable.zip` as
artifacts. (Mac builds via CI are out of scope until macOS runners are
added.)

## Project layout

```
SubtitleCleaner/
├── main.py                          # Entry point
├── requirements.txt                  # PySide6 + python-mpv + qtawesome
├── requirements-whisper.txt          # optional: faster-whisper
├── requirements-llm.txt              # optional: google-generativeai + groq
├── requirements-visual.txt           # optional: nudenet + onnxruntime
├── core/
│   ├── paths.py                     # source vs frozen-build path resolution
│   ├── scanner.py                   # orchestrates the scan
│   ├── audio_extractor.py           # ffmpeg wrapper to pull WAV audio
│   ├── subtitle_extractor.py        # extract embedded subs from MKV
│   ├── subtitle_parser.py           # parse .srt / .vtt
│   ├── transcriber.py               # faster-whisper subprocess wrapper
│   ├── llm_classifier.py            # LLM context analysis orchestrator
│   ├── llm/                         # Ollama / Gemini / Groq backends
│   ├── visual_scanner.py            # NudeNet subprocess wrapper
│   ├── filter_engine.py             # match results against wordlists
│   ├── profile.py                   # save/load per-video filter profiles
│   ├── settings.py                  # JSON-persisted user preferences
│   └── feature_installer.py         # in-app installer for optional ML deps
├── data/
│   ├── wordlists/                   # editable text files, one word per line
│   └── profiles/                    # auto-generated JSON profiles
├── ui/
│   ├── main_window.py               # Open/Scan/Review/Play toolbar
│   ├── scan_dialog.py               # progress dialog
│   ├── review_dialog.py             # category cards + flag table
│   ├── settings_dialog.py           # Scan / Player / Appearance / Features
│   ├── player_widget.py             # mpv playback + mute/skip scheduling
│   ├── theme.py + styles/dark.qss   # dark theme
│   └── icons.py                     # qtawesome icon helpers
├── build/
│   ├── SubtitleCleaner.spec         # Windows PyInstaller spec
│   ├── SubtitleCleanerMac.spec      # macOS .app bundle spec
│   ├── build.bat                    # Windows one-click PyInstaller
│   ├── build_mac.sh                 # macOS one-click PyInstaller
│   └── bin/, bin_mac/               # auto-populated bundle binaries
├── installer/
│   ├── SubtitleCleaner.iss          # Inno Setup script
│   ├── download_deps.ps1            # Windows: libmpv + ffmpeg
│   ├── download_deps_mac.sh         # macOS: brew + dylibbundler
│   └── build_dmg.sh                 # macOS: create-dmg
├── scripts/
│   └── setup_mac.sh                 # one-time Mac setup walkthrough
├── .github/workflows/build-installer.yml   # cloud build
├── MAKE_INSTALLER.bat               # Windows one-click full pipeline
├── MAKE_INSTALLER.command           # macOS one-click full pipeline
└── docs/
    ├── USAGE.md
    └── MAC_BUILD.md
```

## How filtering works

Each flag is `(start_ms, end_ms, word, category, action, flag_type, confidence, reason)`.
`action` is `mute` (default for audio) or `skip` (default for visual).
`flag_type` is `audio` or `visual`. During playback the player observes
mpv's `time-pos` property and either mutes audio (via mpv's buffer-aware
`mute` property) or seeks past the range when the position enters a flag.

A small **padding** (default 250 ms) is applied around each flag so the
cut isn't audible at the edges. Adjust in `core/filter_engine.py`.

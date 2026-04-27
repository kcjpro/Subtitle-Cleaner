# Subtitle Cleaner

A standalone desktop video player that scans video files for profanity, blasphemy,
and sexually explicit language, then mutes or skips flagged sections during playback.

Inspired by ClearPlay. Designed for personal/family use.

## Features (MVP)

- Plays MP4, MKV, AVI, MOV, and other formats supported by VLC.
- Pre-scans the video for objectionable content using:
  - **Embedded subtitles** in MKV files (extracted via ffmpeg).
  - **Sidecar subtitle files** (`movie.srt`, `movie.vtt`) next to the video.
  - **Audio transcription** with [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
    when no subtitles are available (or when a thorough scan is requested).
- Categorizes flagged words into **blasphemy**, **vulgarity**, **sexual**, and **slurs**
  using editable word lists in `data/wordlists/`.
- Admin **review dialog** lets a parent/admin enable/disable each flag before playback.
- Saves a **filter profile** per video in `data/profiles/` so you only review once.
- During playback, the player **mutes** or **skips** the chosen ranges automatically.

## Future / Stubs

- Visual nudity detection via [NudeNet](https://github.com/notAI-tech/NudeNet) on sampled frames.
- LLM-based context classifier (e.g. distinguish "damn the torpedoes" from a curse).
- Password-protected admin mode so only the admin can change filter settings.

## Requirements

- Windows, macOS, or Linux
- [VLC media player](https://www.videolan.org/) installed (provides codecs + playback engine)
- [FFmpeg](https://ffmpeg.org/) on PATH (for audio + subtitle extraction)
- Python 3.10+

## Install (source mode)

```bash
pip install -r requirements.txt
```

That gives you the **subtitle-only** scanner (sidecar `.srt`/`.vtt` and
embedded MKV subtitle tracks). Optional: enable audio transcription for
videos with no subtitles at all:

```bash
pip install -r requirements-whisper.txt
```

The first time you transcribe, faster-whisper downloads a model (~140 MB
for `base`). Tune the model in `core/transcriber.py`.

## Run

```bash
python main.py
```

Open a video, click **Scan**, review flags in the admin dialog, then click **Play**.

## Build a one-click Windows installer

There are two ways to produce `SubtitleCleaner-Setup.exe`:

### Option A — let GitHub build it for you (recommended)

Push the project to a free GitHub repo. The included
[`.github/workflows/build-installer.yml`](.github/workflows/build-installer.yml)
spins up a clean Windows VM, builds the bundle, runs Inno Setup, and
hands you `SubtitleCleaner-Setup.exe` as a downloadable artifact from
the **Actions** tab. No local build environment needed.

Full walkthrough: [`.github/README.md`](.github/README.md).

### Option B — build it locally on Windows

```bat
MAKE_INSTALLER.bat
```

The script downloads ffmpeg + the latest VLC installer, builds the slim
PyInstaller bundle, and wraps it all in an Inno Setup installer at
`installer\Output\SubtitleCleaner-Setup.exe` (~120 MB).

One-time setup on the build machine: Python 3.10–3.12 and
[Inno Setup](https://jrsoftware.org/isdl.php) (free, ~5 MB).

See `installer\README.md` for the full installer story.

### Either way

The end-user double-clicks `SubtitleCleaner-Setup.exe` → wizard → done.
The wizard installs Subtitle Cleaner, creates Start Menu shortcuts, and
silently installs VLC if it's not already present.

### Just want the .exe folder, not an installer?

```bat
build\build.bat
```

Produces a portable `build\dist\SubtitleCleaner\` folder (~50–80 MB)
that you can zip and share. VLC must be installed separately on the
target machine. See `build\README.md`.

The bundled .exe is **subtitle-only** by design — `faster-whisper` and
its native deps don't bundle cleanly with PyInstaller. For transcription,
run from source.

## Project layout

```
SubtitleCleaner/
├── main.py                 # Entry point
├── requirements.txt
├── core/
│   ├── paths.py            # source vs frozen-build path resolution
│   ├── scanner.py          # Orchestrates the scan
│   ├── audio_extractor.py  # ffmpeg wrapper to pull WAV audio
│   ├── subtitle_extractor.py  # extract embedded subs from MKV
│   ├── subtitle_parser.py  # parse .srt / .vtt
│   ├── transcriber.py      # faster-whisper wrapper (word timestamps)
│   ├── filter_engine.py    # match transcript/subs against word lists
│   └── profile.py          # save/load per-video filter profiles
├── data/
│   ├── wordlists/          # editable text files, one word per line
│   └── profiles/           # auto-generated JSON profiles
├── ui/
│   ├── main_window.py      # Open/Scan/Review/Play
│   ├── scan_dialog.py      # progress dialog
│   ├── review_dialog.py    # flag table with on/off toggles
│   └── player_widget.py    # VLC playback + mute scheduling
├── build/
│   ├── SubtitleCleaner.spec  # PyInstaller spec
│   ├── build.bat             # one-click Windows build
│   ├── build_exe.py          # cross-platform build script
│   ├── bin/                  # drop ffmpeg.exe + ffprobe.exe here to bundle
│   └── README.md             # build instructions
├── installer/
│   ├── SubtitleCleaner.iss   # Inno Setup script (with VLC detection)
│   ├── download_deps.ps1     # auto-fetches VLC + ffmpeg
│   ├── deps/                 # auto-populated; or drop installers here manually
│   └── README.md             # installer instructions
├── .github/
│   ├── workflows/build-installer.yml  # cloud build (Windows runner)
│   └── README.md             # GitHub Actions setup walkthrough
├── MAKE_INSTALLER.bat        # one-click full pipeline → setup.exe (local build)
└── docs/USAGE.md
```

## How filtering works

Each flag is a record of `(start_time, end_time, word, category, action)` where
`action` is `mute` (default) or `skip`. During playback the player polls the
current position; when it enters a flag's range it either mutes audio or seeks
past the range. When the range ends, audio is restored.

A small **padding** (default 150 ms) is applied around each flag so the cut
isn't audible at the edges. Adjust in `core/filter_engine.py`.

# Usage

## 1. Easiest path — click-to-run

Grab the prebuilt installer or portable for your OS from
[GitHub Releases](https://github.com/kcjpro/Subtitle-Cleaner/releases) (or
build it yourself with `MAKE_INSTALLER.bat` on Windows /
`MAKE_INSTALLER.command` on macOS — see
[build/README.md](../build/README.md) and [docs/MAC_BUILD.md](MAC_BUILD.md)).

The click-to-run app is the **slim** build:

- Subtitle scanning (sidecar + embedded MKV/MP4 tracks)
- Video playback with mute/skip via libmpv
- Modern dark UI

It does **not** include the heavy optional features by default. Open
**Settings -> Optional Features** to install any of these on demand:

- **Audio transcription (Whisper)** — word-level timestamps when a video
  has no subtitle track.
- **LLM context analysis** — Gemini / Groq / Ollama can flag implied
  sexual or disturbing content beyond wordlist matches.
- **Visual nudity scanning (NudeNet)** — flag nude/sexual frames with no
  dialogue.

The in-app installer creates a sibling Python environment for you (it
needs system Python 3.10+ on PATH); you don't have to touch pip yourself.

## 2. Running from Python source

If you'd rather run from source (faster iteration when developing):

**System:**

- **mpv / libmpv** — playback engine.
  - Windows: download `libmpv-2.dll` from a recent
    [shinchiro mpv build](https://github.com/shinchiro/mpv-winbuild-cmake/releases)
    (extract from `mpv-dev-x86_64-*.7z`) and drop it into `bin/` next to
    the app (or onto PATH).
  - macOS: `brew install mpv ffmpeg`
  - Linux: `apt install libmpv2 ffmpeg` (Debian/Ubuntu) or your distro equivalent.
- **FFmpeg** on PATH (used to extract audio, subtitles, and frames).
  - Windows: grab a build from
    [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add the `bin/` folder to PATH.

**Python:**

```bash
pip install -r requirements.txt
```

That's enough to run the app with subtitle-based scanning.

To enable the heavier optional features (same set the in-app installer
covers):

```bash
pip install -r requirements-whisper.txt   # word-level audio transcription
pip install -r requirements-llm.txt       # cloud LLMs (Gemini, Groq)
pip install -r requirements-visual.txt    # NudeNet visual scanning
```

The first scan that uses transcription downloads a `faster-whisper` model
(~1.5 GB for `medium`). This happens once per model.

## 3. Launch from source

```bash
python main.py
```

## 4. Workflow

1. **Open video** (toolbar -> folder icon, or `Ctrl+O`). Pick an `.mp4`, `.mkv`,
   `.avi`, etc.
2. **Preferences** (`Ctrl+,`) — first time only. Pick:
   - Whisper model (`medium` is the default sweet spot on a modern GPU).
   - LLM context backend if you want context-aware flagging
     (Ollama, Gemini, or Groq) plus an API key for cloud backends.
   - Whether to run NudeNet for visual nudity detection.
   - **Optional Features** tab: install Whisper / LLM / NudeNet on demand
     if you're running from a click-to-run build.
3. **Scan** (`Ctrl+S`). The scanner runs each enabled detection source:
   - Audio transcription (Whisper) -> wordlist matching.
   - LLM context analysis on the transcript (optional).
   - NudeNet frame sampling (optional).
   All results merge into one flag list.
4. **Review filters**. The dialog shows every match — timestamp, type
   (audio/visual), category, the matched word/phrase, the surrounding
   context, an LLM confidence bar (when applicable), and a per-flag toggle.
   Use the bulk checkboxes at the top to enable/disable a whole category
   at once. Choose `mute` (silence audio) or `skip` (jump past the range)
   per flag. Visual flags are always skip-only.
   Click **Save & Play**.
5. **Play**. mpv handles the playback. The widget watches `time-pos` and
   applies the active filter immediately when you cross into a flagged
   range. A red `MUTED (category)` badge appears next to the time when
   audio is being suppressed.

Filter profiles are saved automatically in `data/profiles/`. Re-opening the
same video reuses its profile, so you only review once.

## 5. Detection sources

| Source       | What it catches                              | Cost                     |
|--------------|----------------------------------------------|--------------------------|
| Subtitles    | Anything in the wordlists, cue-level timing  | Free, fast               |
| Whisper      | Profanities + word-level timestamps          | ~1-2 min/movie on GPU    |
| LLM context  | Implied sex / innuendo / disturbing dialogue | Free tier or Ollama      |
| NudeNet      | On-screen nudity (visual)                    | ~30s/movie at 1 fps      |

You can stack any combination.

## 6. Editing wordlists

Wordlists live in `data/wordlists/`:

- `blasphemy.txt`
- `vulgarity.txt`
- `sexual.txt`
- `slurs.txt`

One word or short phrase per line. Lines starting with `#` are comments.
Matching is **case-insensitive** and uses **word boundaries**.

After editing wordlists, re-scan any video to pick up the changes.

## 7. Settings file

`data/settings.json` holds your preferences (Whisper model, LLM backend,
API keys, NudeNet toggle, theme). API keys may also be supplied via
environment variables (`GEMINI_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY`)
which take priority over the saved values.

## 8. Troubleshooting

- **"python-mpv could not be loaded"** — `libmpv-2.dll` isn't reachable.
  Drop it into `bin/` next to the app.
- **No video shows but audio plays** — same as above; libmpv version mismatch
  or missing DLL.
- **LLM backend not reachable** — start your Ollama server (`ollama serve`)
  for the local backend, or supply an API key for Gemini/Groq.
- **No flags found** — open the saved JSON in `data/profiles/`. The `notes`
  field tells you which sources ran and how many flags each produced.
- **Scan is slow** — Whisper transcription is the slow part; pick a smaller
  model in Preferences, or supply a sidecar `.srt` to skip transcription.

## 9. What's next

- Hover-thumbnail previews on the scrubber.
- Speaker-aware filtering.
- Encrypted API key vault.

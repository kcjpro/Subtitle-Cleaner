# Usage

## 1. Install prerequisites

**System:**

- [VLC media player](https://www.videolan.org/) (any recent version). The app
  uses VLC as its playback engine via `python-vlc`.
- [FFmpeg](https://ffmpeg.org/download.html) on PATH (used to extract audio
  and embedded subtitles). On Windows you can grab a build from
  [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add the `bin/` folder
  to your PATH.

**Python:**

```bash
pip install -r requirements.txt
```

The first scan that uses transcription will download a `faster-whisper` model
(~140 MB for `base`). This happens once per model.

## 2. Launch

```bash
python main.py
```

## 3. Workflow

1. **Open video** (toolbar → folder icon, or `Ctrl+O`). Pick an `.mp4`, `.mkv`,
   `.avi`, etc.
2. **Scan** (`Ctrl+S`). The scanner looks for content in this order:
   1. A sidecar subtitle file: `My Movie.srt` next to `My Movie.mkv`.
   2. An embedded subtitle track (typical for MKV).
   3. Audio transcription via faster-whisper.
   The first source that produces results is used.
3. **Review filters**. The review dialog shows every match — timestamp,
   category, the matched word, the surrounding context, and a per-flag toggle.
   Use the bulk checkboxes at the top to enable/disable a whole category at
   once. Choose `mute` (silence audio) or `skip` (jump past the range) per flag.
   Click **Save & Play**.
4. **Play**. While playing, the player polls position every ~80 ms and applies
   the active filter. A red `MUTED (category)` badge appears next to the time
   when audio is being suppressed.

Filter profiles are saved automatically in `data/profiles/`. Re-opening the
same video reuses its profile, so you only review once.

## 4. Editing wordlists

Wordlists live in `data/wordlists/`:

- `blasphemy.txt`
- `vulgarity.txt`
- `sexual.txt`
- `slurs.txt`

One word or short phrase per line. Lines starting with `#` are comments.
Matching is **case-insensitive** and uses **word boundaries**, so `damn` will
match "Damn" but not "Amsterdam". Multi-word phrases like `god damn` are
matched as a phrase before the single word `damn`.

After editing wordlists, re-scan any video to pick up the changes (the existing
profile is replaced).

## 5. Tuning

In `core/filter_engine.py`:
- `DEFAULT_PADDING_MS` — extra silence/skip applied around each flag.
- `default_action_by_category` in `scan_segments()` — change which categories
  default to `mute` vs `skip`.

In `core/transcriber.py`:
- `DEFAULT_MODEL` — `tiny`, `base`, `small`, `medium`, `large-v3`. Larger is
  more accurate but slower. CPU works for `tiny`/`base`; `medium` and up
  effectively need a GPU.

## 6. Troubleshooting

- **"faster-whisper not installed; skipping transcription."** — `pip install
  faster-whisper`. Or rely on subtitles only.
- **No video shows but audio plays** — VLC likely isn't installed, or
  `python-vlc` can't find the libraries. Install VLC and restart.
- **No flags found, but you expected some** — check `data/profiles/` for the
  generated JSON. The `notes` field tells you which source was used and how
  many segments it produced. If it says "no source", neither subtitles nor
  transcription worked.
- **Scan is very slow** — transcription is the slow part. Try a smaller model
  (`tiny` or `base`), or supply subtitles to skip transcription entirely.

## 7. What's not yet built

- Visual nudity detection (planned via NudeNet on sampled frames).
- Password-protected admin mode.
- Live re-classification using a local LLM (to handle context like "damn the
  torpedoes").

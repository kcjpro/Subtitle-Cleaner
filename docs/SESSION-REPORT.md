# Session Report: Subtitle Cleaner — Playback & Transcription Overhaul

**Date:** April 27–28, 2026
**Repo:** [kcjpro/Subtitle-Cleaner](https://github.com/kcjpro/Subtitle-Cleaner)
**Commit:** `ac6018e` on `master`

---

## What We Started With

The Subtitle Cleaner application could load a video, scan it using subtitle files, and identify flagged words in a review dialog. However, the core playback features — **muting** and **skipping** vulgar content — were completely non-functional during video playback.

## What We Fixed

### 1. Mute/Skip Actually Works Now (player_widget.py)

| Problem | Root Cause | Fix |
|---------|-----------|-----|
| Muting did nothing | `audio_set_mute(True)` is unreliable on Windows VLC | Switched to `audio_set_volume(0)` with saved volume restore |
| Skip didn't advance | Playback timer re-triggered the same flag | Set time to `end + 50ms`, clear active flag after skip |
| Unmute left volume at 0 | No volume state saved before muting | Track `_saved_volume` before zeroing volume |

### 2. Whisper GPU Transcription (transcriber.py)

Subtitle-based timestamps were too coarse for precise muting, so we integrated `faster-whisper` with GPU acceleration:

- **Model upgrade:** `base` → `medium` for significantly better word detection
- **GPU path:** CUDA float16 on RTX 4090, automatic CPU int8 fallback
- **CUDA DLL discovery:** Auto-finds `nvidia-cublas-cu12` and `nvidia-cudnn-cu12` bin directories at runtime
- **VAD filter disabled:** `vad_filter=True` was silently dropping short utterances that contained profanity — the exact content we need to catch

### 3. Subprocess Isolation (transcriber.py — major refactor)

The app was crashing with `0xC0000005` (access violation) after transcription completed. The CUDA context from `ctranslate2` was corrupting VLC's native state.

**Solution:** Whisper now runs in a **completely separate Python process**:
- Main process spawns a child via `subprocess.Popen`
- Child loads the model, transcribes, writes results to a temp JSON file
- Child sends `PROGRESS:0.xx` lines via stdout for the progress bar
- When the child exits, all GPU memory is truly freed — no CUDA artifacts remain

### 4. Subtitle Toggle (player_widget.py)

Added a **CC button** to the player controls that toggles embedded subtitle track visibility on/off, so users don't read the words that are being muted.

### 5. Save & Play Auto-Resume (main_window.py)

After clicking "Save & Play" in the review dialog, playback now automatically starts instead of requiring a separate play click.

### 6. Padding Increase (filter_engine.py)

Default flag padding increased from `150ms` → `250ms` to give a slightly wider buffer around flagged words with Whisper's precise word-level timestamps.

### 7. Scanner Priority (scanner.py)

Added `prefer_transcription` option (default `True`). When enabled, the scanner tries Whisper first for word-level timestamps, falling back to subtitles only if transcription is unavailable. Extracted transcription logic into `_try_transcription()` helper.

## Files Changed

| File | Lines Changed | Summary |
|------|:---:|---------|
| `core/transcriber.py` | +121 / -49 | Subprocess isolation, VAD fix, CUDA env setup |
| `core/scanner.py` | +48 / -37 | Whisper-first scan flow, extracted helper |
| `ui/player_widget.py` | +52 / -13 | Volume muting, skip fix, CC button, pre-roll |
| `ui/main_window.py` | +1 | Auto-play after save |
| `core/filter_engine.py` | +1 / -1 | Padding 150→250ms |

## Known Limitations

1. **Mute timing precision** — VLC occasionally reports timestamps that don't perfectly align with speaker output, causing mutes to feel slightly early or late. This appears to be a VLC-level issue with certain media files.
2. **VLC audio warnings** — Some files produce `"too low audio sample frequency"` or `"Timestamp conversion failed"` warnings from VLC's internal demuxer. These don't crash the app but may affect timing.
3. **Whisper transcription time** — The `medium` model on GPU takes roughly 1-2 minutes for a full-length movie. CPU fallback is significantly slower.
4. **No hybrid merge yet** — Subtitle detection and Whisper detection are separate paths; a future enhancement could merge both sources to maximize coverage and timing accuracy.

## Architecture After Changes

```
User loads video
    ↓
Scanner (scanner.py)
    ├─ prefer_transcription=True → Whisper subprocess
    │     ├─ Extract WAV (ffmpeg)
    │     ├─ Spawn child process
    │     ├─ Child: load model (GPU/CPU), transcribe, write JSON
    │     └─ Parent: read progress, parse results
    └─ fallback → Sidecar subtitles → Embedded subtitles
    ↓
Filter Engine: match words against wordlists → Flag list
    ↓
Review Dialog: user enables/disables flags, picks mute/skip
    ↓
Player Widget: polls position, applies mute (volume=0) or skip (set_time)
```

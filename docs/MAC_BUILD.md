# Building Subtitle Cleaner on macOS

Builds an `.app` bundle plus an installer `.dmg` and a portable `.zip`.

PyInstaller cannot cross-compile, so a Mac is required. The build script
auto-detects whether you're on Apple Silicon (arm64) or Intel (x86_64)
and produces a native binary for that arch.

## TL;DR

From a clone of the repo:

```bash
bash scripts/setup_mac.sh
bash MAKE_INSTALLER.command
```

The first command sets up Homebrew, Python 3.12, mpv, ffmpeg, and a
project venv. The second runs the full build.

Outputs land in `installer/Output/`:

| File | Purpose |
|------|---------|
| `SubtitleCleaner.dmg` | Drag-to-Applications installer |
| `SubtitleCleaner-mac.zip` | Portable `.app`, unzip + double-click |

## What the setup script installs

`scripts/setup_mac.sh` is idempotent — re-running it only installs what's
missing. It checks for / installs:

1. **Xcode Command Line Tools** (clang, git, `install_name_tool`, `codesign`).
2. **Homebrew** itself.
3. **brew formulas:**
   - `python@3.12` — the build uses 3.12 specifically (PySide6 + PyInstaller
     wheels are most reliable on 3.12 in 2026).
   - `mpv` — provides `libmpv.2.dylib`.
   - `ffmpeg` — provides `ffmpeg` and `ffprobe` binaries.
   - `dylibbundler` — rewrites dylib install names so they relocate cleanly
     into the `.app` bundle's `Contents/Frameworks/` folder.
   - `create-dmg` — builds the .dmg with a drag-to-Applications layout.
4. **Project venv** at `.build-env-mac/` containing `PySide6`,
   `python-mpv`, `qtawesome`, `pyinstaller`.

Re-run any time a brew formula updates or you wipe `.build-env-mac/`.

## Step-by-step (if you want to inspect each phase)

```bash
# 1. Stage libmpv + transitive dylibs into build/bin_mac/, plus ffmpeg/ffprobe.
bash installer/download_deps_mac.sh

# 2. Run PyInstaller against build/SubtitleCleanerMac.spec.
bash build/build_mac.sh

# 3. Wrap build/dist/SubtitleCleaner.app in a .dmg.
bash installer/build_dmg.sh
```

## What the .app bundle looks like

```
SubtitleCleaner.app/Contents/
    Info.plist                    (CFBundleIdentifier=com.subtitlecleaner.app)
    MacOS/
        SubtitleCleaner           (PyInstaller launcher)
    Frameworks/
        libmpv.2.dylib            (+ transitive dylibs, install names rewritten)
    Resources/
        bin/
            ffmpeg
            ffprobe
        data/
            wordlists/*.txt       (editable in place)
            profiles/             (created at runtime)
```

PyInstaller bundles its own Python runtime + `PySide6` + `python-mpv`
inside the `.app`, so users do **not** need to brew-install anything to
run it.

## First-launch Gatekeeper warning

The build is **not codesigned or notarized** (it would need an Apple
Developer account at $99/yr). macOS will block the first launch with:

> "SubtitleCleaner.app" can't be opened because it is from an
> unidentified developer.

The `.dmg` ships with a `README.txt` explaining the workaround:

```bash
# Right-click the .app -> Open, then click "Open" in the dialog.
# Or, from Terminal:
xattr -dr com.apple.quarantine /Applications/SubtitleCleaner.app
```

After the first successful open, the app launches normally from
Spotlight / Launchpad / dock.

## Troubleshooting

**`brew: command not found` after install** — the installer printed two
lines telling you to add `eval "$(/opt/homebrew/bin/brew shellenv)"` to
your shell profile. Either run those, or close and reopen Terminal.

**`python-mpv could not be loaded`** — libmpv isn't installed or wasn't
copied into the bundle. Run `brew reinstall mpv` then re-run
`bash installer/download_deps_mac.sh`.

**Black video pane on launch** — the bundled `libmpv.2.dylib` works, but
its transitive dylibs aren't relocated correctly. `dylibbundler` should
handle this, but if it failed silently, inspect:

```bash
otool -L SubtitleCleaner.app/Contents/Frameworks/libmpv.2.dylib
```

Anything pointing to `/opt/homebrew/...` or `/usr/local/...` is bad —
those need to be rewritten to `@loader_path/...`. Re-run
`installer/download_deps_mac.sh`.

**App opens then immediately quits** — run from Terminal to see the
crash:

```bash
/Applications/SubtitleCleaner.app/Contents/MacOS/SubtitleCleaner
```

A common cause is a Python wheel mismatch between your venv's Python and
the runtime — wipe `.build-env-mac/` and re-run `setup_mac.sh`.

**Universal2 (arm64 + x86_64) build** — out of scope for v1. Build on
each arch separately. Combining is possible via `lipo` but PyInstaller's
support is fragile.

## Optional: ML/AI features after install

The slim build does **not** ship faster-whisper / NudeNet / cloud LLM
SDKs — those add ~2 GB and break PyInstaller's analysis pass. After
installing the .app, open **Settings → Optional Features** to install
them on demand into a per-user environment.

If you'd rather run from Python source (faster iteration when developing):

```bash
source .build-env-mac/bin/activate
pip install -r requirements-whisper.txt
pip install -r requirements-llm.txt
pip install -r requirements-visual.txt
python main.py
```

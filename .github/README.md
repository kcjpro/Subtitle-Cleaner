# GitHub Actions: build the Windows installer in the cloud

`workflows/build-installer.yml` builds `SubtitleCleaner-Setup.exe` on a
clean Windows 2022 VM every time you push code, and uploads the .exe
as a downloadable artifact you can grab from the Actions tab.

You don't need a Windows machine, Python, Inno Setup, or any local build
environment. GitHub does it all.

## One-time setup

1. **Create a GitHub account** at <https://github.com/> if you don't
   have one. Free.

2. **Create a new repo** at <https://github.com/new>. Any name; private
   is fine. *Don't* let GitHub initialize it with a README — we want an
   empty repo so we can push the project as-is.

3. **Push the project**. From inside the `Subtitle Cleaner` folder on
   your Windows machine:

   ```bat
   cd "E:\Claude CoWork Projects\Subtitle Cleaner\Subtitle Cleaner"
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```

   (If you don't have git, install it from <https://git-scm.com/>.
   Or use [GitHub Desktop](https://desktop.github.com/) which is a
   GUI for the same thing — open the project folder, "Add" then "Publish
   repository".)

4. **Wait for the build**. The push triggers the workflow automatically.
   Go to the **Actions** tab in your repo to watch it run. First build
   takes ~5 minutes (later builds are faster — pip cache).

## Getting the .exe

Once the workflow is green:

1. Click the workflow run.
2. Scroll to the bottom — there's an **Artifacts** section.
3. Click **SubtitleCleaner-Setup** to download `SubtitleCleaner-Setup.exe`
   (zipped by GitHub; just unzip).

That's the file you hand to anyone for one-click install.

There's also a **SubtitleCleaner-Portable** artifact with the unwrapped
folder if you'd rather distribute that.

## Triggering a build manually

Don't want to push code to trigger? Go to **Actions → Build Windows
installer → Run workflow** (top-right). Pick a branch, click run.

## Cutting a release with a downloadable installer

When you're ready to publish a version:

1. **Releases** tab → **Draft a new release**.
2. Pick a tag (e.g., `v1.0.0`), title it, write some notes.
3. Click **Publish release**.

The workflow runs again and **attaches `SubtitleCleaner-Setup.exe`
directly to the release**, so anyone visiting your GitHub releases page
can download it with one click — no need to dig into Actions artifacts.

## Editing the workflow

The whole pipeline lives in `workflows/build-installer.yml`. It mirrors
what `MAKE_INSTALLER.bat` does locally:

1. Set up Python 3.12.
2. Install runtime + PyInstaller deps.
3. Run `installer/download_deps.ps1` to pull VLC + ffmpeg.
4. Mirror ffmpeg into `build/bin/`.
5. Run `pyinstaller` against `build/SubtitleCleaner.spec`.
6. Run `iscc` against `installer/SubtitleCleaner.iss`.
7. Upload `SubtitleCleaner-Setup.exe` as an artifact (and attach to
   release if this run was triggered by a release publish).

If you change `SubtitleCleaner.spec`, `download_deps.ps1`, or the
.iss script, the workflow picks up the changes automatically on the
next push.

## Why not just build locally?

You can — `MAKE_INSTALLER.bat` still works for that. GitHub Actions just
removes the friction:

- Always builds in a clean Python 3.12 environment (no env mess to debug)
- Inno Setup is preinstalled on the runner
- No local build artifacts cluttering your machine
- Builds happen automatically when you push changes
- Anyone you grant repo access to can build, no Windows box required

Files in this folder are auto-downloaded by MAKE_INSTALLER.bat
(via installer\download_deps.ps1):

  libmpv-2.dll    - bundled into the app, drives video playback
  ffmpeg.exe      - bundled into the app
  ffprobe.exe     - bundled into the app

You can also drop any of these here manually if you'd rather use a specific
version or if you have no internet on the build machine. The download script
skips anything already present.

Sources:
  - libmpv: https://github.com/shinchiro/mpv-winbuild-cmake/releases
            (look for the latest mpv-dev-x86_64-*.7z, extract libmpv-2.dll)
  - ffmpeg: https://www.gyan.dev/ffmpeg/builds/  (release essentials)

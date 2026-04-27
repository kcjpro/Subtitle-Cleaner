Files in this folder are auto-downloaded by MAKE_INSTALLER.bat
(via installer\download_deps.ps1):

  vlc-installer.exe   - latest 64-bit VLC installer (~45 MB)
  ffmpeg.exe          - bundled into the app
  ffprobe.exe         - bundled into the app

You can also drop any of these here manually if you'd rather use a specific
version or if you have no internet on the build machine. The download script
skips anything already present.

Sources:
  - VLC:    https://www.videolan.org/vlc/download-windows.html
  - ffmpeg: https://www.gyan.dev/ffmpeg/builds/  (release essentials)

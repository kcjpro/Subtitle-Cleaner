Drop ffmpeg.exe and ffprobe.exe in this folder to have them bundled
with the built app.

Where to get them:
  https://www.gyan.dev/ffmpeg/builds/   (look for "release essentials")
  Or:
  https://www.ffmpeg.org/download.html

After downloading the build, copy these two files from the archive's bin/
folder into THIS folder, then run build.bat (or build_exe.py).

If you skip this step, the built app will look for ffmpeg/ffprobe on the
user's PATH at runtime instead.

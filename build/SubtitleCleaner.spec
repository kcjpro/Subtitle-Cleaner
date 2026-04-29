# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Subtitle Cleaner — slim subtitle-only build.

Run from the build/ folder:
    pyinstaller --noconfirm --clean SubtitleCleaner.spec

Result lands in build/dist/SubtitleCleaner/. Zip the folder to share.

This build is intentionally subtitle-only. The transcription path
(faster-whisper / ctranslate2), the LLM SDKs, and NudeNet are excluded
because bundling them pulls in ~1 GB of fragile native deps. To use those
features, run the app from Python source after installing the relevant
optional requirements files.
"""

from pathlib import Path

# PyInstaller injects SPECPATH as the directory containing this spec.
SPEC_DIR = Path(SPECPATH).resolve()
PROJECT_ROOT = SPEC_DIR.parent

# ---------- bundled binaries ----------

binaries = []

# If the user dropped ffmpeg.exe / ffprobe.exe / libmpv-2.dll into build/bin/,
# ship them in the bundled bin/ folder so the runtime path resolution finds
# them first.
bin_dir = SPEC_DIR / "bin"
for name in (
    "ffmpeg.exe", "ffprobe.exe", "ffmpeg", "ffprobe",
    "libmpv-2.dll", "mpv-2.dll", "libmpv-1.dll",
):
    src = bin_dir / name
    if src.exists():
        binaries.append((str(src), "bin"))

# ---------- data files ----------

datas = []

# Ship the editable wordlists alongside the exe.
wordlist_src = PROJECT_ROOT / "data" / "wordlists"
for txt in wordlist_src.glob("*.txt"):
    datas.append((str(txt), "data/wordlists"))

# Ship the optional requirements files so the in-app feature installer
# (Settings -> Optional Features) can pip-install them into a sibling
# venv without rebuilding the app.
for req in ("requirements-whisper.txt", "requirements-llm.txt", "requirements-visual.txt"):
    req_path = PROJECT_ROOT / req
    if req_path.exists():
        datas.append((str(req_path), "."))

# ---------- hidden imports ----------

# Only the things the slim runtime actually needs.
hiddenimports = ["mpv", "qtawesome"]

# ---------- excludes ----------

# Aggressively exclude every ML/data-science package and its friends, even if
# the build env happens to have them installed. This keeps the bundle small
# and makes the build deterministic.
excludes = [
    # Transcription stack
    "faster_whisper",
    "ctranslate2",
    "onnxruntime",
    "onnx",
    "nudenet",
    "huggingface_hub",
    "tokenizers",
    "transformers",
    "safetensors",
    "tensorboard",
    "tensorboardX",

    # NVIDIA CUDA libraries (pulled in transitively by faster-whisper /
    # torch / etc. on machines that have them installed). Each is
    # 100-300 MB and we don't ship the GPU transcription stack anyway.
    "nvidia",
    "nvidia.cublas",
    "nvidia.cudnn",
    "nvidia.cuda_runtime",
    "nvidia.cuda_nvrtc",
    "nvidia.cuda_cupti",
    "nvidia.cufft",
    "nvidia.curand",
    "nvidia.cusolver",
    "nvidia.cusparse",
    "nvidia.nccl",
    "nvidia.nvjitlink",
    "nvidia.nvtx",

    # Cloud LLM SDKs (optional in source mode only).
    "google",
    "google.generativeai",
    "groq",

    # Deep learning frameworks
    "torch",
    "torchvision",
    "torchaudio",
    "tensorflow",
    "jax",
    "jaxlib",
    "flax",

    # Numeric / scientific (we don't use any of it)
    "numpy",
    "scipy",
    "pandas",
    "matplotlib",
    "sklearn",
    "scikit_learn",
    "sympy",
    "numba",
    "cupy",

    # Notebook / interactive
    "IPython",
    "ipywidgets",
    "jupyter",
    "jupyter_client",
    "jupyter_core",
    "notebook",

    # HTTP / async we don't use
    "aiohttp",
    "anyio",
    "httpx",
    "httpcore",
    "trio",
    "h2",
    "fsspec",
    "requests",  # we don't make HTTP calls
    "urllib3",
    "chardet",
    "certifi",

    # Misc heavy deps that get pulled in transitively
    "av",          # PyAV - we use ffmpeg.exe directly instead
    "pyarrow",
    "fastapi",
    "starlette",
    "uvicorn",
    "click",
    "typer",
    "rich",
    "markdown_it",
    "mdurl",
    "pygments",
    "yaml",
    "PIL",
    "fastai",

    # Test frameworks
    "pytest",
    "_pytest",

    # Build/setup helpers
    "setuptools",
    "pip",
    "wheel",
    "distutils",
]

# ---------- analysis ----------

block_cipher = None

a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SubtitleCleaner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,         # GUI app — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,             # set to a path/to/icon.ico to brand the exe
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SubtitleCleaner",
)

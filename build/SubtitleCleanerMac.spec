# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Subtitle Cleaner — macOS .app bundle.

Run from the build/ folder:
    pyinstaller --noconfirm --clean SubtitleCleanerMac.spec

Result lands in build/dist/SubtitleCleaner.app/. Wrap it in a .dmg for
distribution (see installer/build_dmg.sh).

This is the slim build, mirror of SubtitleCleaner.spec on Windows. It
intentionally excludes faster-whisper / NudeNet / cloud LLM SDKs; users
opt in to those at runtime via the in-app installer.
"""

from pathlib import Path

# PyInstaller injects SPECPATH as the directory containing this spec.
SPEC_DIR = Path(SPECPATH).resolve()
PROJECT_ROOT = SPEC_DIR.parent

# ---------- bundled binaries ----------
#
# build/bin_mac/ is the Mac equivalent of build/bin/. installer/download_deps_mac.sh
# populates it with libmpv.2.dylib (and its transitive dylibs, rewritten
# via dylibbundler with @loader_path/ install names so they can live
# next to one another), plus ffmpeg and ffprobe binaries. We expect a
# flat layout - everything sits directly under bin_mac/.
#
# Each file is classified by extension:
#   *.dylib / libmpv*  ->  bundle's Frameworks/ folder
#   anything else      ->  bundle's bin/ folder (lands in Resources/bin/)

binaries = []
bin_dir = SPEC_DIR / "bin_mac"
if bin_dir.exists():
    for path in sorted(bin_dir.iterdir()):
        if not path.is_file():
            continue
        if path.suffix == ".dylib" or path.name.startswith("libmpv"):
            binaries.append((str(path), "Frameworks"))
        else:
            binaries.append((str(path), "bin"))

# ---------- data files ----------

datas = []
wordlist_src = PROJECT_ROOT / "data" / "wordlists"
for txt in wordlist_src.glob("*.txt"):
    datas.append((str(txt), "data/wordlists"))

# Ship the requirements files so the in-app feature installer can pip
# install heavy optional deps into a sibling venv after first launch.
for req in ("requirements-whisper.txt", "requirements-llm.txt", "requirements-visual.txt"):
    req_path = PROJECT_ROOT / req
    if req_path.exists():
        datas.append((str(req_path), "."))

# ---------- hidden imports ----------

hiddenimports = ["mpv", "qtawesome"]

# ---------- excludes ----------

excludes = [
    "faster_whisper", "ctranslate2", "onnxruntime", "onnx", "nudenet",
    "huggingface_hub", "tokenizers", "transformers", "safetensors",
    "tensorboard", "tensorboardX",
    "google", "google.generativeai", "groq",
    "torch", "torchvision", "torchaudio", "tensorflow", "jax", "jaxlib", "flax",
    "numpy", "scipy", "pandas", "matplotlib", "sklearn", "scikit_learn",
    "sympy", "numba", "cupy",
    "IPython", "ipywidgets", "jupyter", "jupyter_client", "jupyter_core",
    "notebook",
    "aiohttp", "anyio", "httpx", "httpcore", "trio", "h2", "fsspec",
    "requests", "urllib3", "chardet", "certifi",
    "av", "pyarrow", "fastapi", "starlette", "uvicorn",
    "click", "typer", "rich", "markdown_it", "mdurl", "pygments", "yaml",
    "PIL", "fastai",
    "pytest", "_pytest",
    "setuptools", "pip", "wheel", "distutils",
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,         # host arch (arm64 on Apple Silicon, x86_64 on Intel)
    codesign_identity=None,
    entitlements_file=None,
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

# ---------- .app bundle ----------

app = BUNDLE(
    coll,
    name="SubtitleCleaner.app",
    icon=None,
    bundle_identifier="com.subtitlecleaner.app",
    version="2.0.0",
    info_plist={
        "CFBundleName": "Subtitle Cleaner",
        "CFBundleDisplayName": "Subtitle Cleaner",
        "CFBundleVersion": "2.0.0",
        "CFBundleShortVersionString": "2.0.0",
        "CFBundleIdentifier": "com.subtitlecleaner.app",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
        "LSApplicationCategoryType": "public.app-category.video",
        "NSAppleEventsUsageDescription": "Subtitle Cleaner does not use AppleEvents.",
    },
)

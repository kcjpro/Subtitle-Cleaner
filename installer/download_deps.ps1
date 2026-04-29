<#
.SYNOPSIS
  Download libmpv-2.dll + ffmpeg into installer\deps\ so the bundled
  installer/portable build has everything it needs.

  v2 dropped python-vlc in favour of python-mpv. The bundle now ships
  libmpv-2.dll directly (no separate end-user installer step).
#>

$ErrorActionPreference = 'Stop'
$ProgressPreference   = 'SilentlyContinue'

$here    = Split-Path -Parent $MyInvocation.MyCommand.Path
$depsDir = Join-Path $here 'deps'
if (-not (Test-Path $depsDir)) { New-Item -ItemType Directory -Path $depsDir | Out-Null }

# ----------------------------------------------------------------------
# ffmpeg
# ----------------------------------------------------------------------
$ffmpegExe  = Join-Path $depsDir 'ffmpeg.exe'
$ffprobeExe = Join-Path $depsDir 'ffprobe.exe'
if ((Test-Path $ffmpegExe) -and (Test-Path $ffprobeExe)) {
    Write-Host "ffmpeg + ffprobe already present, skipping download."
} else {
    Write-Host "Downloading ffmpeg (release essentials)..."
    $zip = Join-Path $depsDir 'ffmpeg-release-essentials.zip'
    Invoke-WebRequest 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' `
                      -OutFile $zip -UseBasicParsing

    $extract = Join-Path $depsDir '_ffmpeg_extract'
    if (Test-Path $extract) { Remove-Item -Recurse -Force $extract }
    Expand-Archive -Path $zip -DestinationPath $extract -Force

    Get-ChildItem -Path $extract -Recurse -Filter 'ffmpeg.exe'  | Select-Object -First 1 |
        ForEach-Object { Copy-Item $_.FullName -Destination $ffmpegExe  -Force }
    Get-ChildItem -Path $extract -Recurse -Filter 'ffprobe.exe' | Select-Object -First 1 |
        ForEach-Object { Copy-Item $_.FullName -Destination $ffprobeExe -Force }

    Remove-Item -Recurse -Force $extract
    Remove-Item -Force $zip
    Write-Host "ffmpeg + ffprobe ready in $depsDir"
}

# ----------------------------------------------------------------------
# libmpv-2.dll (shinchiro Windows build, GitHub releases)
# ----------------------------------------------------------------------
$libmpvDll = Join-Path $depsDir 'libmpv-2.dll'
if (Test-Path $libmpvDll) {
    Write-Host "libmpv-2.dll already present, skipping download."
} else {
    # Override with $env:LIBMPV_URL to pin a specific build.
    $libmpvUrl = $env:LIBMPV_URL

    if (-not $libmpvUrl) {
        # Resolve the newest mpv-dev-x86_64-*.7z asset from the latest
        # release of shinchiro/mpv-winbuild-cmake. We deliberately skip
        # the "-v3-" variant (AVX2 only) for max CPU compatibility.
        Write-Host "Querying GitHub for the latest libmpv build..."
        $apiUrl = 'https://api.github.com/repos/shinchiro/mpv-winbuild-cmake/releases/latest'
        $headers = @{
            'User-Agent' = 'SubtitleCleaner-build-script'
            'Accept'     = 'application/vnd.github+json'
        }

        try {
            $release = Invoke-RestMethod -Uri $apiUrl -Headers $headers -UseBasicParsing
        } catch {
            throw "Could not query GitHub API at $apiUrl ($_). Set `$env:LIBMPV_URL to a direct .7z download URL and re-run."
        }

        $asset = $release.assets |
            Where-Object { $_.name -match '^mpv-dev-x86_64-\d{8}.*\.7z$' -and $_.name -notmatch '-v3-' } |
            Select-Object -First 1
        if (-not $asset) {
            throw "Could not find a mpv-dev-x86_64-*.7z asset in $($release.tag_name). Set `$env:LIBMPV_URL to override."
        }

        $libmpvUrl = $asset.browser_download_url
        Write-Host "Latest libmpv: $($asset.name)"
    }

    Write-Host "Downloading $libmpvUrl"
    $archive = Join-Path $depsDir 'mpv-dev-x86_64.7z'
    Invoke-WebRequest $libmpvUrl -OutFile $archive -UseBasicParsing -MaximumRedirection 10

    # Extract libmpv-2.dll. We try Windows' built-in tar (bsdtar via
    # libarchive) first since it ships on Win10/11. If that fails, fall
    # back to 7z.exe if available on PATH.
    $extract = Join-Path $depsDir '_mpv_extract'
    if (Test-Path $extract) { Remove-Item -Recurse -Force $extract }
    New-Item -ItemType Directory -Path $extract | Out-Null

    $extracted = $false

    # Strategy 1: 7-Zip if available (handles 7z natively).
    $sevenZipCmd = $null
    foreach ($n in @('7z', '7z.exe', '7za.exe')) {
        $found = Get-Command $n -ErrorAction SilentlyContinue
        if ($found) { $sevenZipCmd = $found.Source; break }
    }
    if (-not $sevenZipCmd) {
        foreach ($candidate in @(
            "$env:ProgramFiles\7-Zip\7z.exe",
            "${env:ProgramFiles(x86)}\7-Zip\7z.exe"
        )) {
            if (Test-Path $candidate) { $sevenZipCmd = $candidate; break }
        }
    }
    if ($sevenZipCmd) {
        Write-Host "Extracting with 7-Zip ($sevenZipCmd)..."
        & $sevenZipCmd x -y -o"$extract" $archive | Out-Null
        $check = Get-ChildItem -Path $extract -Recurse -Filter 'libmpv-2.dll' | Select-Object -First 1
        if ($check) { $extracted = $true }
    }

    # Strategy 2: Python + py7zr. Python is already a build prerequisite,
    # and py7zr is a tiny pure-Python LZMA-aware 7z reader.
    if (-not $extracted) {
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCmd) { $pythonCmd = Get-Command py -ErrorAction SilentlyContinue }
        if ($pythonCmd) {
            Write-Host "7-Zip not found; using Python + py7zr to extract..."
            & $pythonCmd.Source -m pip install --quiet --disable-pip-version-check py7zr 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $py = "import py7zr, sys; py7zr.SevenZipFile(sys.argv[1], 'r').extractall(sys.argv[2])"
                & $pythonCmd.Source -c $py $archive $extract
                if ($LASTEXITCODE -eq 0) {
                    $check = Get-ChildItem -Path $extract -Recurse -Filter 'libmpv-2.dll' | Select-Object -First 1
                    if ($check) { $extracted = $true }
                }
            }
        }
    }

    # Strategy 3: tar (Windows 10/11 ships bsdtar/libarchive). Often
    # fails with "LZMA codec is unsupported" but cheap to try last.
    if (-not $extracted) {
        Write-Host "Trying tar as last resort..."
        & tar -xf $archive -C $extract 2>$null
        if ($LASTEXITCODE -eq 0) {
            $check = Get-ChildItem -Path $extract -Recurse -Filter 'libmpv-2.dll' | Select-Object -First 1
            if ($check) { $extracted = $true }
        }
    }

    if (-not $extracted) {
        throw "Could not extract $archive. Install 7-Zip from https://www.7-zip.org/ (default options) or pip install py7zr, then re-run."
    }

    $found = Get-ChildItem -Path $extract -Recurse -Filter 'libmpv-2.dll' |
        Select-Object -First 1
    Copy-Item $found.FullName -Destination $libmpvDll -Force

    Remove-Item -Recurse -Force $extract
    Remove-Item -Force $archive
    Write-Host "libmpv-2.dll ready in $depsDir"
}

Write-Host ""
Write-Host "All deps ready in $depsDir"

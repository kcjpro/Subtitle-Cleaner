<#
.SYNOPSIS
  Download VLC + ffmpeg installers/binaries into installer\deps\
  so the bundled installer build has everything it needs.
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
# VLC (Win64 latest)
# ----------------------------------------------------------------------
$vlcInstaller = Join-Path $depsDir 'vlc-installer.exe'
if (Test-Path $vlcInstaller) {
    Write-Host "VLC installer already present, skipping download."
} else {
    $base = 'https://download.videolan.org/pub/videolan/vlc/last/win64/'
    Write-Host "Locating latest VLC installer at $base ..."
    $listing = (Invoke-WebRequest $base -UseBasicParsing).Content
    $match   = [regex]::Match($listing, 'vlc-[\d.]+-win64\.exe')
    if (-not $match.Success) {
        throw "Could not find VLC installer link at $base"
    }
    $url = $base + $match.Value
    Write-Host "Downloading $url"
    Invoke-WebRequest $url -OutFile $vlcInstaller -UseBasicParsing
    Write-Host "VLC installer saved to $vlcInstaller"
}

Write-Host ""
Write-Host "All deps ready in $depsDir"

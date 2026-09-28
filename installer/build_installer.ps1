<#
.SYNOPSIS
    Build BIMAP release artifacts using PyInstaller.

.DESCRIPTION
    Builds a portable single-file EXE and/or an onedir folder for use with
    Inno Setup. All output lands in installer/dist/.

.PARAMETER Version
    Version string to embed in the portable filename  (e.g. "0.3.0")

.PARAMETER PortableOnly
    Skip the onedir build. Useful for quick CI/local portable testing.

.PARAMETER SkipInnoSetup
    Skip the Inno Setup step even in a full build.

.EXAMPLE
    # Portable EXE only
    .\installer\build_installer.ps1 -Version 0.2.0 -PortableOnly

    # Full build (portable + onedir + Inno Setup)
    .\installer\build_installer.ps1 -Version 0.2.0
#>
param(
    [Parameter(Mandatory)][string]$Version,
    [switch]$PortableOnly,
    [switch]$SkipInnoSetup
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root      = Split-Path -Parent $PSScriptRoot    # repo root
$PyI       = Join-Path $Root ".venv\Scripts\pyinstaller.exe"
$DistPath  = Join-Path $Root "installer\dist"
$BuildPath = Join-Path $Root "installer\build"

# ---------------------------------------------------------------------------
# 0. Sanity check
# ---------------------------------------------------------------------------
if (-not (Test-Path $PyI)) {
    Write-Error "pyinstaller not found at '$PyI'. Run: pip install pyinstaller"
}

# ---------------------------------------------------------------------------
# 1. Build portable single-file EXE
# ---------------------------------------------------------------------------
Write-Host "[1/3] Building portable BIMAP.exe (onefile)..." -ForegroundColor Cyan
& $PyI installer\bimap_portable.spec `
    --distpath $DistPath `
    --workpath $BuildPath `
    --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller portable build failed (exit $LASTEXITCODE)" }

$exeSrc = Join-Path $DistPath "BIMAP.exe"
$exeDst = Join-Path $Root "BIMAP-v${Version}-windows-x64-portable.exe"
Move-Item -Force $exeSrc $exeDst
Write-Host "    -> $exeDst" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 2. Optionally build onedir folder and zip it
# ---------------------------------------------------------------------------
if (-not $PortableOnly) {
    Write-Host "[2/3] Building onedir BIMAP folder..." -ForegroundColor Cyan
    & $PyI installer\bimap.spec `
        --distpath $DistPath `
        --workpath $BuildPath `
        --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller onedir build failed (exit $LASTEXITCODE)" }

    $zipSrc = Join-Path $DistPath "BIMAP"
    $zipDst = Join-Path $Root "BIMAP-v${Version}-windows-x64.zip"
    Compress-Archive -Path "$zipSrc\*" -DestinationPath $zipDst -Force
    Write-Host "    -> $zipDst" -ForegroundColor Green
} else {
    Write-Host "[2/3] Skipped onedir build (-PortableOnly)." -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# 3. Optionally run Inno Setup
# ---------------------------------------------------------------------------
if (-not $PortableOnly -and -not $SkipInnoSetup) {
    $iss  = Join-Path $Root "installer\bimap_setup.iss"
    $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    if (-not (Test-Path $iscc)) { $iscc = "${env:ProgramFiles}\Inno Setup 6\ISCC.exe" }

    if (-not (Test-Path $iss)) {
        Write-Warning "[3/3] No bimap_setup.iss found - skipping Inno Setup."
    } elseif (-not (Test-Path $iscc)) {
        Write-Warning "[3/3] Inno Setup 6 not found - skipping installer generation."
    } else {
        Write-Host "[3/3] Running Inno Setup..." -ForegroundColor Cyan
        & $iscc $iss /DMyAppVersion=$Version
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed (exit $LASTEXITCODE)" }
    }
} else {
    Write-Host "[3/3] Skipped Inno Setup." -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Build complete." -ForegroundColor Green
Write-Host "  Portable EXE : BIMAP-v${Version}-windows-x64-portable.exe"
if (-not $PortableOnly) {
    Write-Host "  Folder ZIP   : BIMAP-v${Version}-windows-x64.zip"
}

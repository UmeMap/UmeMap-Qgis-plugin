# build.ps1 - UmeMap QGIS Plugin Builder

# Hitta QGIS plugin-mapp
$qgisBase = "$env:APPDATA\QGIS\QGIS3\profiles"
$qgisPluginPath = $null

if (Test-Path $qgisBase) {
    $profiles = Get-ChildItem $qgisBase -Directory
    if ($profiles.Count -eq 1) {
        $qgisPluginPath = Join-Path $profiles[0].FullName "python\plugins\UmeMap"
    }
    elseif ($profiles.Count -gt 1) {
        Write-Host "`n  Flera QGIS-profiler hittades:" -ForegroundColor Yellow
        for ($i = 0; $i -lt $profiles.Count; $i++) {
            Write-Host "  [$($i+1)] $($profiles[$i].Name)" -ForegroundColor White
        }
        $profileChoice = Read-Host "`n  Vilken profil?"
        $idx = [int]$profileChoice - 1
        if ($idx -ge 0 -and $idx -lt $profiles.Count) {
            $qgisPluginPath = Join-Path $profiles[$idx].FullName "python\plugins\UmeMap"
        }
    }
}

if (-not $qgisPluginPath) {
    $qgisPluginPath = Read-Host "  QGIS plugin-mapp hittades inte. Ange sökväg"
    $qgisPluginPath = Join-Path $qgisPluginPath "UmeMap"
}

# Auto-versioning från git-taggar
$today = Get-Date -Format "yyyyMMdd"
$now = Get-Date -Format "HHmm"
$latestTag = git describe --tags --abbrev=0 --match "v*" 2>$null

if ($latestTag) {
    $tagVersion = $latestTag.TrimStart('v')
    $parts = $tagVersion -split '\.'
    $major = [int]$parts[0]
    $minor = [int]$parts[1]

    # Kolla om HEAD är exakt på taggen
    $tagCommit = git rev-list -n 1 $latestTag
    $headCommit = git rev-parse HEAD
    if ($tagCommit -eq $headCommit) {
        # Produktions-build: exakt på tagg, bara datum
        $version = "$major.$minor+$today"
    } else {
        # Dev-build: efter tagg, datum + tid för unika versioner
        $version = "$major.$($minor + 1)+$today.$now"
    }
} else {
    Write-Host "  Ingen v*-tagg hittad. Ange version manuellt i metadata.txt" -ForegroundColor Red
    exit 1
}

# Uppdatera metadata.txt med ny version och changelog
$metaContent = Get-Content ".\metadata.txt" -Raw
$metaContent = $metaContent -replace '(?m)^version=.*$', "version=$version"

# Generera changelog från commits sedan senaste taggen
if ($tagCommit -ne $headCommit) {
    $commits = git log --no-merges "$latestTag..HEAD" --pretty=format:"  - %s" 2>$null
    if ($commits) {
        $newEntry = "  $version`n$commits"
        $metaContent = $metaContent -replace '(?ms)^changelog=.*?(?=\r?\n[#a-z])', "changelog=`n$newEntry"
    }
}

Set-Content ".\metadata.txt" -Value $metaContent -NoNewline

Write-Host ""
Write-Host "  UmeMap Plugin Builder  v$version" -ForegroundColor Cyan
Write-Host "  =================================" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  [1] Snabbdeploy till QGIS" -ForegroundColor Green
Write-Host "      Kopierar till plugin-mappen direkt" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  [2] Bygg ZIP-paket" -ForegroundColor Yellow
Write-Host "      Skapar deploy/UmeMap-$version.zip" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  [3] Båda (snabbdeploy + ZIP)" -ForegroundColor Magenta
Write-Host "      Kopierar till QGIS och skapar ZIP" -ForegroundColor DarkGray
Write-Host ""

$choice = Read-Host "  Välj [1/2/3]"

function Compile-Resources {
    Write-Host "  Kompilerar resurser (pyrcc5)..." -ForegroundColor Cyan
    pyrcc5 -o resources.py resources.qrc
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  pyrcc5 misslyckades. Kontrollera att pyrcc5 finns i PATH." -ForegroundColor Red
        exit 1
    }
}

function Deploy-ToQgis {
    Write-Host "`n  Kopierar till QGIS plugin-mapp..." -ForegroundColor Cyan
    Compile-Resources

    if (-not (Test-Path $qgisPluginPath)) {
        New-Item -ItemType Directory -Path $qgisPluginPath -Force | Out-Null
    }

    Remove-Item "$qgisPluginPath\*" -Recurse -Force -ErrorAction SilentlyContinue

    $filesToCopy = @(
        "__init__.py", "plugin.py",
        "resources.py", "UmeMap_dialog_base.ui",
        "metadata.txt", "icon.png"
    )
    foreach ($file in $filesToCopy) {
        if (Test-Path $file) { Copy-Item $file -Destination $qgisPluginPath }
    }

    $dirs = @("core", "features", "ui", "icons")
    foreach ($dir in $dirs) {
        if (Test-Path $dir) {
            Copy-Item $dir -Destination $qgisPluginPath -Recurse -Force
        }
    }

    if (Test-Path "../../LICENSE") {
        Copy-Item "../../LICENSE" -Destination $qgisPluginPath
    }

    Write-Host "  Kopierat till $qgisPluginPath" -ForegroundColor Green
    Write-Host "  Ladda om pluginet i QGIS (Plugin Reloader)" -ForegroundColor DarkGray
}

function Build-Zip {
    Write-Host "`n  Bygger ZIP-paket..." -ForegroundColor Cyan
    Compile-Resources

    if (Test-Path "deploy") {
        Remove-Item "deploy" -Recurse -Force
    }

    pb_tool deploy -y
    Copy-Item ../../LICENSE -Destination ./deploy/UmeMap/

    $zipName = "UmeMap-$version.zip"
    $zipPath = $zipName

    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force
    }

    # Compress-Archive saknar directory entries som QGIS kräver, använd Python istället
    python -c @"
import zipfile, os
with zipfile.ZipFile(r'$zipPath', 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk('deploy'):
        for d in dirs:
            dir_path = os.path.join(root, d)
            arcname = os.path.relpath(dir_path, 'deploy') + '/'
            zf.write(dir_path, arcname)
        for f in files:
            file_path = os.path.join(root, f)
            arcname = os.path.relpath(file_path, 'deploy')
            zf.write(file_path, arcname)
"@

    # Flytta ZIP till deploy-mappen
    Move-Item $zipPath "deploy\$zipName"
    Write-Host "  Skapad: deploy\$zipName" -ForegroundColor Green
}

switch ($choice) {
    "1" { Deploy-ToQgis }
    "2" { Build-Zip }
    "3" { Deploy-ToQgis; Build-Zip }
    default {
        Write-Host "`n  Ogiltigt val." -ForegroundColor Red
    }
}

Write-Host ""
Pause

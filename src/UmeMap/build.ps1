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

# Läs version
$meta = Get-Content ".\metadata.txt" | Where-Object { $_ -match '^version=' }
$version = ($meta -split '=')[1].Trim()

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
    $zipPath = Join-Path "deploy" $zipName

    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force
    }

    Compress-Archive -Path "deploy\*" -DestinationPath $zipPath -Force
    Write-Host "  Skapad: $zipPath" -ForegroundColor Green
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

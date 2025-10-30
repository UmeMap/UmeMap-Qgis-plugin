# build.ps1
Write-Host "🚀 Startar build-processen för UmeMap-plugin..." -ForegroundColor Cyan
Write-Host "------------------------------------------------------`n"

# === Läs version från metadata.txt ===
Write-Host "📄 Läser version från metadata.txt..." -ForegroundColor Yellow
$meta = Get-Content ".\metadata.txt" | Where-Object { $_ -match '^version=' }
$version = ($meta -split '=')[1].Trim()
Write-Host "🎯 Version hittad: $version`n" -ForegroundColor Green

# === Rensa gammal deploy-mapp ===
if (Test-Path "deploy") {
    Write-Host "🧹 Tar bort gammal deploy-mapp..." -ForegroundColor Yellow
    Remove-Item "deploy" -Recurse -Force
    Write-Host "✅ Deploy-mapp rensad.`n" -ForegroundColor Green
}
else {
    Write-Host "ℹ️ Ingen tidigare deploy-mapp hittades – hoppar över rensning.`n" -ForegroundColor DarkGray
}

# === Kör pb_tool ===
Write-Host "⚙️  Kör pb_tool deploy... detta kan ta en stund..." -ForegroundColor Cyan
pb_tool deploy -y
Write-Host "✅ pb_tool körning färdig.`n" -ForegroundColor Green

Write-Host "⚙️ Kopiera LICENSE till Deploy mappen"
Copy-Item ../../LICENSE -Destination ./deploy/UmeMap/
Write-Host "✅ Kopierat filen" -ForegroundColor Green

# === Skapa zip-fil ===
Write-Host "📦 Skapar zip-fil..." -ForegroundColor Yellow
$zipName = "UmeMap-$version.zip"
$zipPath = Join-Path "deploy" $zipName

if (Test-Path $zipPath) {
    Write-Host "🗑️  Tar bort gammal zip-fil..." -ForegroundColor Yellow
    Remove-Item $zipPath -Force
}

Compress-Archive -Path "deploy\*" -DestinationPath $zipPath -Force
Write-Host "✅ Zip-fil skapad: $zipPath`n" -ForegroundColor Green

# === Avslutning ===
Write-Host "🎉 Allt klart! Plugin version $version är byggd och packad i:" -ForegroundColor Cyan
Write-Host "   ➜ $zipPath`n"
Write-Host "`n💡 Installera i QGIS via: Plugins > Manage and Install Plugins > Install from ZIP" -ForegroundColor Gray
Write-Host "💾 Deploy-mapp finns kvar för manuell kontroll."


Write-Host "`n------------------------------------------------------"
Write-Host "🏁 Build-processen avslutad!`n" -ForegroundColor Green




Pause

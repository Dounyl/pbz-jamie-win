$ErrorActionPreference = 'Stop'
$exe = Join-Path $PSScriptRoot '.local\dist\JamieWin.Audio.exe'
if (-not (Test-Path -LiteralPath $exe)) { & (Join-Path $PSScriptRoot 'tools\build.ps1') }
$config = Join-Path $PSScriptRoot 'audio.json'
Start-Process -FilePath $exe -ArgumentList @('--config', ('"' + $config + '"')) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
Write-Output 'JamieWin audio started. Launch Phantom Blade Zero normally from Steam.'

param([string]$GameRoot = 'E:\SteamLibrary\steamapps\common\PBZ')
$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$mods = [IO.Path]::GetFullPath((Join-Path $GameRoot 'platform\steam\ue4ss\Mods'))
if (-not (Test-Path -LiteralPath (Join-Path (Split-Path $mods) 'UE4SS.dll'))) { throw 'Install the compatible UE4SS loader first.' }
$destination = Join-Path $mods 'JamieWin'
New-Item -ItemType Directory -Path (Join-Path $destination 'runtime') -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $project 'mods\JamieWin\Scripts') -Destination $destination -Recurse -Force
[IO.File]::WriteAllText((Join-Path $destination 'enabled.txt'), '')
Write-Output "JamieWin scripts installed at $destination. Restart the game to load them."

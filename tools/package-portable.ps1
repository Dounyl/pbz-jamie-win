param([string]$Version = '0.8.0')
$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $project '.local\dist\JamieWin.Audio.exe'
$loader = Join-Path $project '.local\cache\phantombladezero_ue4ss-1195.zip'
if ((Get-FileHash -LiteralPath $loader).Hash -ne '0B6B7F9430502C1FBEADB09740E586063DCE42FE4F7D7A3EE7BE51C9BD6CA304') { throw 'Unverified loader archive.' }
if ((Get-Item -LiteralPath $exe).LastWriteTimeUtc -lt (Get-Item -LiteralPath (Join-Path $project 'src\AudioHost.cs')).LastWriteTimeUtc) { throw 'Rebuild the audio player first.' }
$stage = Join-Path $project ('.local\portable\' + [guid]::NewGuid().ToString('N'))
$full = Join-Path $stage 'Full'
$modOnly = Join-Path $stage 'ModOnly'
$gameBin = Join-Path $full 'platform\steam'
New-Item -ItemType Directory -Path $gameBin -Force | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::ExtractToDirectory($loader, $gameBin)
[IO.File]::WriteAllText((Join-Path $gameBin 'ue4ss\Mods\mods.txt'), "; JamieWin is enabled by its enabled.txt file.`r`n")
$relativeMod = 'platform\steam\ue4ss\Mods\JamieWin'
$mod = Join-Path $full $relativeMod
foreach ($folder in @('Scripts','Player','Audio','runtime')) {
    New-Item -ItemType Directory -Path (Join-Path $mod $folder) -Force | Out-Null
}
Copy-Item -LiteralPath $exe -Destination (Join-Path $mod 'Player')
Get-ChildItem -LiteralPath (Join-Path $project 'mods\JamieWin\Scripts') -Filter '*.lua' | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $mod 'Scripts')
}
foreach ($file in @('mandarin_duck_play.mp3','mr_top_player.m4a','jamie_drink4_ja.wav','jamie_wins.wav')) {
    Copy-Item -LiteralPath (Join-Path $project ('resources\audio\' + $file)) -Destination (Join-Path $mod 'Audio')
}
$original = Get-Content -LiteralPath (Join-Path $project 'audio.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$options = [ordered]@{
    Bridge='runtime/bridge.txt'; Runtime='runtime'
    Music='Audio/mandarin_duck_play.mp3'; ArmedMusic='Audio/mr_top_player.m4a'
    Drink='Audio/jamie_drink4_ja.wav'; Win='Audio/jamie_wins.wav'
    MusicVolume=$original.MusicVolume; DrinkVolume=$original.DrinkVolume
    WinVolume=$original.WinVolume; DuckVolume=$original.DuckVolume
    WatchGame=$true; GameExecutable='../../../PBZ.exe'
}
[IO.File]::WriteAllText((Join-Path $mod 'audio.json'), ($options | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
[IO.File]::WriteAllText((Join-Path $mod 'enabled.txt'), '')
[IO.File]::WriteAllText((Join-Path $mod 'runtime\.keep'), '')
New-Item -ItemType Directory -Path (Split-Path (Join-Path $modOnly $relativeMod)) -Force | Out-Null
Copy-Item -LiteralPath $mod -Destination (Split-Path (Join-Path $modOnly $relativeMod)) -Recurse
$output = Join-Path $project '.local\releases'
New-Item -ItemType Directory -Path $output -Force | Out-Null
$result = [ordered]@{ FullStage=$full; ModOnlyStage=$modOnly; ModRoot=$mod }
foreach ($kind in @('Full','ModOnly')) {
    $folder = Join-Path $stage $kind
    Copy-Item -LiteralPath (Join-Path $project 'packaging\PORTABLE-README.txt') -Destination (Join-Path $folder 'JamieWin-Readme.txt')
    if (Get-ChildItem -LiteralPath $folder -Recurse -File | Where-Object { $_.Extension -in @('.ps1','.cmd','.bat','.vbs') }) { throw 'Unexpected manual launcher in portable package.' }
    $archive = Join-Path $output ('JamieWin-' + $Version + '-' + $kind + '-' + [DateTime]::Now.ToString('yyyyMMdd-HHmmss') + '.zip')
    [IO.Compression.ZipFile]::CreateFromDirectory($folder, $archive)
    [IO.File]::WriteAllText(($archive + '.sha256'), (Get-FileHash -LiteralPath $archive).Hash + '  ' + (Split-Path $archive -Leaf))
    $result[$kind] = $archive
}
[pscustomobject]$result

param([string]$Version = '')
$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$probe = Join-Path $project 'probes\JamieWinNativeAudioTest'
$metadataPath = Join-Path $probe 'mod.json'
$metadata = Get-Content -LiteralPath $metadataPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($metadata.format -ne 1 -or $metadata.id -cne 'JamieWinNativeAudioTest' -or
    $metadata.name -notmatch '^[A-Za-z][A-Za-z0-9_-]*$' -or
    $metadata.version -notmatch '^\d+\.\d+\.\d+$' -or
    $metadata.channel -notmatch '^[a-z][a-z0-9-]*$') { throw 'Invalid mod.json metadata.' }
if ($Version -and $Version -cne $metadata.version) { throw 'Change the version in mod.json; a package override cannot change it.' }
$Version = $metadata.version
$runtimeVersion = $Version + '-' + $metadata.channel
$settingsText = Get-Content -LiteralPath (Join-Path $probe 'Scripts\probe_settings.lua') -Raw
if ($settingsText -notmatch ('Version\s*=\s*"' + [regex]::Escape($runtimeVersion) + '"')) {
    throw 'mod.json version does not match the Lua runtime version.'
}
$nativeText = Get-Content -LiteralPath (Join-Path $probe 'Native\audio.c') -Raw
if ($nativeText -notmatch ('#define\s+VERSION\s+"' + [regex]::Escape($runtimeVersion) + '"')) {
    throw 'mod.json version does not match the native runtime version.'
}
$build = & (Join-Path $PSScriptRoot 'build-native-audio-test.ps1')
$stage = Join-Path $project ('.local\native-audio-test\' + [guid]::NewGuid().ToString('N'))
$mod = Join-Path $stage ('platform\steam\ue4ss\Mods\' + $metadata.id)
foreach ($folder in @('Scripts','Audio','Native','runtime')) {
    New-Item -ItemType Directory -Path (Join-Path $mod $folder) -Force | Out-Null
}
foreach ($name in @('main.lua','probe_settings.lua','gameplay.lua','native_audio.lua','game_audio.lua','executions.lua')) {
    Copy-Item -LiteralPath (Join-Path $probe ('Scripts\' + $name)) -Destination (Join-Path $mod 'Scripts')
}
foreach ($name in @('core.lua','weapon.lua','settings.lua')) {
    Copy-Item -LiteralPath (Join-Path $project ('mods\JamieWin\Scripts\' + $name)) -Destination (Join-Path $mod 'Scripts')
}
foreach ($name in @('mandarin_duck_play.wav','mr_top_player.wav','jamie_drink4_ja.wav','jamie_wins.wav')) {
    Copy-Item -LiteralPath (Join-Path $build.Output $name) -Destination (Join-Path $mod 'Audio')
}
Copy-Item -LiteralPath $build.DLL -Destination (Join-Path $mod 'Native')
Copy-Item -LiteralPath $metadataPath -Destination (Join-Path $mod 'mod.json')
[IO.File]::WriteAllText((Join-Path $mod 'enabled.txt'), '')
[IO.File]::WriteAllText((Join-Path $mod 'runtime\.keep'), '')
Copy-Item -LiteralPath (Join-Path $project 'packaging\NATIVE-AUDIO-TEST-README.txt') -Destination (Join-Path $stage 'JamieWin-NativeAudioTest-Readme.txt')

$unexpected = Get-ChildItem -LiteralPath $stage -File -Recurse | Where-Object {
    $_.Extension -notin @('.lua','.wav','.txt','.dll','.json') -and $_.Name -ne '.keep'
}
if ($unexpected) { throw 'Unexpected file in native-only test package.' }
$dlls = @(Get-ChildItem -LiteralPath $stage -Filter '*.dll' -File -Recurse)
if ($dlls.Count -ne 1 -or $dlls[0].Name -ne 'JamieWinAudio.dll') { throw 'Unexpected native DLL.' }
$stamp = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'China Standard Time').ToString('yyyyMMdd-HHmmss')
$output = Join-Path $project ('.local\releases\' + $stamp)
New-Item -ItemType Directory -Path $output -Force | Out-Null
# UE MM 1.4.1 splits a dotted version at the END into separate Name and Version fields.
# Keep build dates in the enclosing folder, not in the manager's displayed mod name.
$archive = Join-Path $output ($metadata.name + '-' + $Version + '.zip')
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory($stage, $archive)
$hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText(($archive + '.sha256'), $hash + '  ' + (Split-Path $archive -Leaf) + "`n", (New-Object Text.UTF8Encoding($false)))
[pscustomobject]@{ Archive=$archive; SHA256=$hash; Stage=$stage; ModRoot=$mod; Name=$metadata.name; Version=$Version }

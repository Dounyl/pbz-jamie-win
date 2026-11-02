param([string]$Compiler = '', [string]$FFmpeg = '')
$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
if (-not $Compiler) { $Compiler = Join-Path $project '.local\cache\native-build\ziglang\zig.exe' }
if (-not $FFmpeg) { $FFmpeg = Join-Path $project '.local\cache\audio-tools\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe' }
if (-not (Test-Path -LiteralPath $Compiler)) { throw 'Zig 0.13.0 required. Install into .local/cache/native-build or pass -Compiler.' }
if (-not (Test-Path -LiteralPath $FFmpeg)) { throw 'FFmpeg required for build-time PCM conversion; pass -FFmpeg.' }
$output = Join-Path $project '.local\native-audio-build'
New-Item -ItemType Directory -Force -Path $output | Out-Null
$env:ZIG_GLOBAL_CACHE_DIR = Join-Path $project '.local\cache\zig-global'
$env:ZIG_LOCAL_CACHE_DIR = Join-Path $project '.local\cache\zig-local'
$source = Join-Path $project 'probes\JamieWinNativeAudioTest\Native\audio.c'
$mixer = Join-Path $project 'probes\JamieWinNativeAudioTest\Native\mixer.c'
$filter = Join-Path $project 'probes\JamieWinNativeAudioTest\Native\menu_filter.c'
$dll = Join-Path $output 'JamieWinAudio.dll'
& $Compiler cc -target x86_64-windows-gnu -std=c11 -O2 -Wall -Wextra -Werror -shared $source $mixer $filter -lwinmm -o $dll
if ($LASTEXITCODE -ne 0) { throw 'Native audio DLL build failed.' }
foreach ($inputName in @('mr_top_player.m4a','mandarin_duck_play.mp3','jamie_drink4_ja.wav','jamie_wins.wav')) {
    $inputPath = Join-Path $project ('resources\audio\' + $inputName)
    $wave = Join-Path $output ([IO.Path]::GetFileNameWithoutExtension($inputName) + '.wav')
    & $FFmpeg -hide_banner -loglevel error -nostdin -y -i $inputPath -map 0:a:0 -vn -map_metadata -1 -ac 2 -ar 48000 -c:a pcm_s16le $wave
    if ($LASTEXITCODE -ne 0) { throw ('PCM conversion failed: ' + $inputName) }
}
[pscustomobject]@{Output=$output; DLL=$dll; CompilerVersion=(& $Compiler version)}

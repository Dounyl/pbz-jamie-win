$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot 'build.ps1')
& python (Join-Path $project 'tests\test_lua.py')
if ($LASTEXITCODE -ne 0) { throw 'Lua tests failed.' }
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $compiler /nologo /target:exe /platform:x64 ('/reference:' + (Join-Path $project '.local\dist\JamieWin.Audio.exe')) ('/out:' + (Join-Path $project '.local\dist\ProtocolTests.exe')) (Join-Path $project 'tests\ProtocolTests.cs')
if ($LASTEXITCODE -ne 0) { throw 'Protocol test compilation failed.' }
& (Join-Path $project '.local\dist\ProtocolTests.exe')
if ($LASTEXITCODE -ne 0) { throw 'Protocol tests failed.' }
& (Join-Path $project '.local\dist\JamieWin.Audio.exe') --config (Join-Path $project 'audio.json') --check
if ($LASTEXITCODE -ne 0) { throw 'Audio decoding check failed.' }

$ErrorActionPreference = 'Stop'
$config = Join-Path $PSScriptRoot 'audio.json'
$process = Start-Process -FilePath (Join-Path $PSScriptRoot '.local\dist\JamieWin.Audio.exe') -ArgumentList @('--config', ('"' + $config + '"'), '--stop') -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw 'Could not request audio shutdown.' }

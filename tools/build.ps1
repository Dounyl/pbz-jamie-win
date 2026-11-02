$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$framework = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319'
$compiler = Join-Path $framework 'csc.exe'
$dist = Join-Path $project '.local\dist'
New-Item -ItemType Directory -Path $dist -Force | Out-Null
$references = @(
    ('/reference:' + (Join-Path $framework 'WPF\PresentationCore.dll')),
    ('/reference:' + (Join-Path $framework 'WPF\WindowsBase.dll')),
    ('/reference:' + (Join-Path $framework 'System.Xaml.dll')),
    ('/reference:' + (Join-Path $framework 'System.Web.Extensions.dll'))
)
& $compiler /nologo /target:winexe /platform:x64 /optimize+ @references ('/out:' + (Join-Path $dist 'JamieWin.Audio.exe')) (Join-Path $project 'src\AudioHost.cs')
if ($LASTEXITCODE -ne 0) { throw 'Audio companion compilation failed.' }
Write-Output (Join-Path $dist 'JamieWin.Audio.exe')

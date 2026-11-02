param(
    [string]$GameRoot = 'E:\SteamLibrary\steamapps\common\PBZ'
)
$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$source = Join-Path $project '.local\cache\loader-1195'
$target = [IO.Path]::GetFullPath((Join-Path $GameRoot 'platform\steam'))
if (-not (Test-Path -LiteralPath (Join-Path $target 'PBZ.exe'))) { throw 'Game executable not found.' }
if (Get-Process -Name PBZ -ErrorAction SilentlyContinue) { throw 'Close Phantom Blade Zero before installation.' }
foreach ($name in @('dwmapi.dll', 'ue4ss')) {
    if (Test-Path -LiteralPath (Join-Path $target $name)) { throw "Existing $name detected; refusing to overwrite it." }
}
if (-not (Test-Path -LiteralPath (Join-Path $source 'ue4ss\UE4SS.dll'))) { throw 'Verified loader package is missing.' }
# Start with only development key bindings. Do not enable bundled gameplay mods.
[IO.File]::WriteAllText((Join-Path $source 'ue4ss\Mods\mods.txt'), "Keybinds : 1`r`n")
Copy-Item -LiteralPath (Join-Path $source 'dwmapi.dll') -Destination $target
Copy-Item -LiteralPath (Join-Path $source 'ue4ss') -Destination $target -Recurse
$manifest = Get-ChildItem -LiteralPath $source -File -Recurse | ForEach-Object {
    $relative = $_.FullName.Substring($source.Length + 1)
    [pscustomobject]@{ path = $relative; sha256 = (Get-FileHash -LiteralPath (Join-Path $target $relative)).Hash }
}
$record = [pscustomobject]@{ target = $target; version = 'v3.0.1-1195-g1ceefac8'; files = @($manifest) }
[IO.File]::WriteAllText((Join-Path $project '.local\cache\loader-install.json'), ($record | ConvertTo-Json -Depth 4))
Write-Output "Installed UE4SS into $target; original game files were not replaced."

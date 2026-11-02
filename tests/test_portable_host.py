"""Check the drop-in player's default config, single instance, and game lifetime."""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
build = json.loads((ROOT / '.local/portable/latest-build.json').read_text(encoding='utf-8-sig'))
work = ROOT / '.local/portable-smoke' / ("路径 with 'spaces' & " + str(time.time_ns()))
game_bin = work / 'platform/steam'
mod = game_bin / 'ue4ss/Mods/JamieWin'
shutil.copytree(build['ModRoot'], mod)
exe = mod / 'Player/JamieWin.Audio.exe'
binary = exe.read_bytes()
pe = struct.unpack_from('<I', binary, 0x3C)[0]
assert struct.unpack_from('<H', binary, pe + 24 + 68)[0] == 2, 'player must use Windows GUI subsystem without console'
config_path = mod / 'audio.json'
config = json.loads(config_path.read_text(encoding='utf-8'))
assert config['WatchGame'] and config['GameExecutable'] == '../../../PBZ.exe'
for field in ('MusicVolume', 'DrinkVolume', 'WinVolume', 'DuckVolume'):
    config[field] = 0
config_path.write_text(json.dumps(config), encoding='utf-8')
fixture_source = work / 'GameFixture.cs'
fixture_source.write_text('class GameFixture { static void Main() { System.Threading.Thread.Sleep(120000); } }', encoding='utf-8')
game_exe = game_bin / 'PBZ.exe'
compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
subprocess.run([str(compiler), '/nologo', '/target:winexe', '/platform:x64', '/out:' + str(game_exe), str(fixture_source)], check=True)
log = mod / 'runtime/audio.log'


def logs():
    return log.read_text(encoding='utf-8-sig') if log.exists() else ''


def until(predicate, message, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.05)
    raise AssertionError(message + '\n' + logs())


game = subprocess.Popen([str(game_exe)], creationflags=subprocess.CREATE_NO_WINDOW)
player = None
try:
    player = subprocess.Popen([str(exe)], cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW)
    until(lambda: f'Watching game process {game.pid};' in logs() and 'armed-music opened' in logs(), 'find exact game and auto-config')
    assert player.poll() is None
    alternate = mod / 'alternate.json'
    alternate.write_text(json.dumps(config), encoding='utf-8')
    duplicate = subprocess.run([str(exe), '--config', str(alternate)], cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
    assert duplicate.returncode == 0 and logs().count('Waiting for game;') == 1, 'one player per game bridge, even across config files'
    game.terminate()
    game.wait(timeout=3)
    assert player.wait(timeout=5) == 0
    assert 'Game exited or unavailable; shutting down audio.' in logs()
    absent = subprocess.run([str(exe)], cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
    assert absent.returncode == 0, 'no background orphan when game is absent'
    print('PASS: windowless executable, portable auto-config, exact game binding, duplicate suppression, auto-exit and no-game exit.')
finally:
    if game.poll() is None:
        game.terminate(); game.wait(timeout=3)
    if player is not None and player.poll() is None:
        player.terminate(); player.wait(timeout=3)

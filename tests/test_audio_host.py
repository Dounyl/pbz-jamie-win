"""Silent end-to-end check of the real WPF player and file handshake."""
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.local' / 'cache' / 'host-smoke'
WORK.mkdir(parents=True, exist_ok=True)
bridge = WORK / 'bridge.txt'
request = WORK / 'audio-request.txt'
runtime = WORK / ('run-' + str(time.time_ns()))
options = json.loads((ROOT / 'audio.json').read_text(encoding='utf-8'))
for field in ('Music', 'ArmedMusic', 'Drink', 'Win'):
    options[field] = str((ROOT / options[field]).resolve())
for field in ('MusicVolume', 'DrinkVolume', 'WinVolume', 'DuckVolume'):
    options[field] = 0
options.update(Bridge=str(bridge), Runtime=str(runtime))
config = WORK / 'audio.json'
config.write_text(json.dumps(options, ensure_ascii=False), encoding='utf-8')
session = 'test' + str(time.time_ns())
seq = 0


def send(state, heavy=0, wins=0, grant='-', track=None):
    global seq
    seq += 1
    if track is None:
        track = 'drunk' if state in ('tipsy', 'drunk') else 'none'
    bridge.write_text(f'JW3|{session}|{seq}|{int(time.time())}|{state}|{heavy}|{wins}|{grant}|{track}|END\n', encoding='ascii')


def lines():
    path = runtime / 'audio.log'
    return path.read_text(encoding='utf-8-sig') if path.exists() else ''


def events():
    return [line[24:] for line in lines().splitlines()]


def heartbeat():
    try:
        value = request.read_text(encoding='ascii').strip().split('|')
        return value if len(value) == 7 and value[1] == session and value[-1] == 'END' else []
    except (OSError, UnicodeError):
        return []


def until(predicate, description, timeout=4):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.025)
    raise AssertionError(description + '\n' + lines())


send('sober')
proc = subprocess.Popen([str(ROOT / '.local' / 'dist' / 'JamieWin.Audio.exe'), '--config', str(config)],
                        cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW,
                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
try:
    until(lambda: 'music opened' in lines() and 'armed-music opened' in lines()
          and heartbeat() and heartbeat()[5] == 'idle', 'startup decode')
    send('sober', track='armed')
    until(lambda: heartbeat() and heartbeat()[5] == 'want', 'held sword requests mute')
    token = heartbeat()[4]
    assert 'armed-music play' not in events(), 'held theme must wait for mute acknowledgement'
    send('sober', grant=token, track='armed')
    until(lambda: 'armed-music play' in events(), 'held theme after grant')
    send('tipsy', grant=token)
    until(lambda: 'music play' in events(), 'switch held theme to drunk theme')
    assert events().index('armed-music stop') < events().index('music play'), 'stop old track before new one'
    assert heartbeat()[4] == token and heartbeat()[5] == 'want', 'track switch must keep game music muted'
    send('sober', grant=token, track='armed')
    until(lambda: events().count('armed-music play') == 2, 'sober returns to held theme')
    assert events().index('music stop') < len(events()) - 1 - events()[::-1].index('armed-music play')
    send('sober')
    until(lambda: heartbeat() and heartbeat()[5] == 'idle', 'putting sword away releases music')
    assert events().count('armed-music stop') == 2
    send('tipsy')
    until(lambda: heartbeat() and heartbeat()[5] == 'want', 'request mute before play')
    token = heartbeat()[4]
    assert events().count('music play') == 1, 'must not play without native mute acknowledgement'
    send('drunk', heavy=1)
    until(lambda: 'drink4 play' in lines(), 'drunk cue must not depend on music mute grant')
    assert events().count('music play') == 1, 'a sound effect must not bypass music mute acknowledgement'
    send('drunk', heavy=1, grant=token)
    until(lambda: events().count('music play') == 2, 'play after matching grant')
    send('tipsy', heavy=1, grant=token)
    until(lambda: 'game=tipsy' in lines().split('music play')[-1], 'tier continuity')
    send('drunk', heavy=1, grant=token)
    send('drunk', heavy=1, wins=1, grant=token)
    until(lambda: 'jamie-win play' in lines(), 'execution voice')
    assert events().count('music play') == 2, 'tier change must not restart music'
    assert lines().count('drink4 play') == 1, 'duplicate counter must not replay drink cue'
    send('sober', heavy=1, wins=1)
    until(lambda: heartbeat() and heartbeat()[5] == 'idle', 'acknowledge stop')
    assert events().count('music stop') == 2, 'music must stop before idle acknowledgement'
    send('tipsy', heavy=1, wins=1, grant=token)
    until(lambda: heartbeat() and heartbeat()[5] == 'want' and heartbeat()[4] != token, 'fresh request after idle')
    new_token = heartbeat()[4]
    assert events().count('music play') == 2, 'old grant must not authorize a new playback'
    send('tipsy', heavy=1, wins=1, grant=new_token)
    until(lambda: events().count('music play') == 3, 'resume with new grant')
    until(lambda: events().count('music stop') == 3, 'lost game heartbeat stops playback', timeout=3)
    (runtime / 'stop').write_text('stop', encoding='ascii')
    assert proc.wait(timeout=5) == 0
    print('PASS: four assets, held/drunk/held switching, stop-before-play, continuous mute lease, both cues, stale grant rejection, watchdog.')
finally:
    if proc.poll() is None:
        (runtime / 'stop').write_text('stop', encoding='ascii')
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.wait(timeout=3)

"""Real Lua C ABI and Windows audio device checks, using generated silence only.

Never starts/controls PBZ. The DSP test separately checks nonzero PCM amplitudes.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import time
import unittest
import uuid
import wave

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / 'probes/JamieWinNativeAudioTest/Scripts'
FFMPEG = ROOT / '.local/cache/audio-tools/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe'
sys.path.insert(0, str(ROOT / '.local/cache/testdeps'))
from lupa.lua54 import LuaRuntime


class DeviceRig:
    def __init__(self, name):
        self.folder = ROOT / '.local/native-audio-test' / (name + '-' + uuid.uuid4().hex)
        for part in ('Native', 'Audio', 'runtime'):
            (self.folder / part).mkdir(parents=True)
        self.dll = self.folder / 'Native/JamieWinAudio.dll'
        shutil.copyfile(ROOT / '.local/native-audio-build/JamieWinAudio.dll', self.dll)
        for name in ('mr_top_player', 'mandarin_duck_play', 'jamie_drink4_ja', 'jamie_wins'):
            self.silence(name)
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.api = {name: self.lua.execute('local p,n=...;return assert(package.loadlib(p,n))',
                                          str(self.dll), 'JamieNative_' + name)
                    for name in ('Init', 'Apply', 'Stop', 'Heartbeat')}
        self.seq = 0
        self.session = 'device-' + uuid.uuid4().hex
        self.values = dict(epoch=1, active=1, track=1, menu=0, allow=0,
                           music=.45, drink_gain=.9, win_gain=1, drink=0, win=0)

    def silence(self, name):
        if not name.startswith('jamie_'):
            extension, codec, rate = ('m4a', 'aac', 48000) if name == 'mr_top_player' else ('mp3', 'libmp3lame', 44100)
            subprocess.run([str(FFMPEG), '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
                            '-f', 'lavfi', '-i', f'anullsrc=r={rate}:cl=stereo', '-t', '0.25',
                            '-c:a', codec, '-b:a', '128k', str(self.folder / 'Audio' / (name + '.' + extension))], check=True)
            return
        with wave.open(str(self.folder / 'Audio' / (name + '.wav')), 'wb') as f:
            f.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
            frames = 48000 if name.startswith('jamie_') else 12000
            f.writeframes(b'\0' * (frames * 4))  # Short music loops; 1 s voices, silence only

    def packet(self, seq=None, session=None, **updates):
        values = {**self.values, **updates}
        fields = ['JWN5', session or self.session, str(seq if seq is not None else self.seq)]
        fields.extend(str(v) for v in values.values())
        return '|'.join(fields) + '|END\n'

    def raw(self, packet):
        (self.folder / 'runtime/native-command.txt').write_bytes(packet.encode('ascii'))
        assert self.api['Apply']() is None

    def apply(self, **updates):
        self.seq += 1
        self.values.update(updates)
        self.raw(self.packet())

    def status(self):
        try:
            return dict(line.split('=', 1) for line in (self.folder / 'runtime/native-status.txt').read_text().splitlines())
        except (FileNotFoundError, PermissionError):
            return {}

    def wait(self, predicate, timeout=5, heartbeat=True):
        deadline = time.monotonic() + timeout
        last = {}
        while time.monotonic() < deadline:
            if heartbeat:
                self.api['Heartbeat']()
            last = self.status()
            if last.get('seq') == str(self.seq) and predicate(last):
                return last
            time.sleep(.025)
        raise AssertionError(f'Device timeout; seq={self.seq}, status={last}, evidence={self.folder}')

    def dwell(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.api['Heartbeat']()
            time.sleep(.025)

    def close(self):
        self.api['Stop']()
        time.sleep(.15)
        print(f'Native device evidence: {self.folder}', flush=True)


class NativeDeviceTests(unittest.TestCase):
    def test_real_mixing_handshake_menu_continuity_cues_gain_stop_and_watchdog(self):
        r = DeviceRig('full-device-check')
        self.assertIsNone(r.api['Init']())
        try:
            s = r.wait(lambda s: s['phase'] == 'idle')
            self.assertEqual(s['pid'], str(os.getpid()))
            r.apply()
            r.wait(lambda s: s['ready'] == '1' and s['music_stopped'] == '1')
            r.dwell(.3)
            self.assertEqual(r.wait(lambda s: True)['samples'], '0', 'Preparation must not queue audio before mute grant')
            r.apply(allow=1)
            s = r.wait(lambda s: s['phase'] == 'playing' and int(s['samples']) > 48000)
            self.assertAlmostEqual(float(s['music_gain']), .648, places=5)
            previous = int(s['music_frames'])
            r.apply(music=.1, drink_gain=.2, win_gain=.3)
            s = r.wait(lambda s: abs(float(s['music_gain'])-.144) < .0001)
            self.assertGreater(int(s['music_frames']), previous, 'Changing sliders must not restart music')
            before_menu = int(s['music_frames'])
            r.apply(menu=1, drink=1, win=1)
            in_menu = r.wait(lambda s: s['phase'] == 'playing' and s['menu_mix'] == '1.000000')
            self.assertGreater(int(in_menu['music_frames']), before_menu)
            r.dwell(.5)
            later = r.wait(lambda s: True)
            self.assertGreater(int(later['samples']), int(in_menu['samples']) + 12000)
            self.assertEqual(later['drink_playing'], '0')
            self.assertEqual(later['win_playing'], '0')
            r.apply(menu=0)
            s = r.wait(lambda s: s['drink_playing'] == '1' and s['win_playing'] == '1')
            self.assertAlmostEqual(float(s['drink_gain']), .2, places=5)
            self.assertAlmostEqual(float(s['music_gain']), .144, places=5, msg='Cues must not duck background music')
            self.assertGreater(int(s['music_frames']), int(later['music_frames']))
            r.wait(lambda s: s['drink_playing'] == '0' and s['win_playing'] == '0' and abs(float(s['music_gain'])-.144) < .0001)
            # Reversing the transition and moving a slider never resets the device or music cursor.
            before_toggle = int(r.wait(lambda s: True)['music_frames'])
            for menu in (1, 0, 1, 0, 1, 0):
                r.apply(menu=menu)
                r.dwell(.06)
            clear = r.wait(lambda s: s['menu_mix'] == '0.000000')
            self.assertGreater(int(clear['music_frames']), before_toggle)
            self.assertEqual((r.folder / 'runtime/native-output.log').read_text().count('READY pid='), 1)
            r.apply(music=0)
            before = int(r.wait(lambda s: True)['samples'])
            r.wait(lambda s: float(s['music_gain']) == 0 and int(s['samples']) > before + 10000)
            r.apply(track=2, music=.45, drink=2)
            # Wait past the normal song-switch fade-in before checking the cue's effect on gain.
            s = r.wait(lambda s: s['track'] == 'drunk' and s['drink_playing'] == '1' and int(s['music_frames']) >= 4800)
            self.assertAlmostEqual(float(s['music_gain']), .45, places=5, msg='Drunk music must also stay at full gain during a cue')
            r.wait(lambda s: s['drink_playing'] == '0')
            log = (r.folder / 'runtime/native-output.log').read_text()
            self.assertEqual(log.count('CUE drink id=1'), 1)
            self.assertEqual(log.count('CUE drink id=2'), 1)
            self.assertEqual(log.count('CUE win id=1'), 1)
            r.apply(track=0, allow=0)
            r.wait(lambda s: s['music_stopped'] == '1')
            r.apply(active=0)
            r.wait(lambda s: s['phase'] == 'idle' and s['ready'] == '0')
            # Coalesced commands, including a player generation change, must acknowledge the last snapshot.
            for track in (1, 2, 1, 0):
                r.apply(active=1, track=track, allow=1, epoch=2)
            r.wait(lambda s: s['track'] == 'none' and s['music_stopped'] == '1')
            r.apply(track=1)
            r.wait(lambda s: s['phase'] == 'playing' and int(s['samples']) > 1000)
            lost = r.wait(lambda s: s['phase'] == 'failed' and s['music_stopped'] == '1', heartbeat=False)
            self.assertEqual(lost['operation'], 'heartbeat_expired')
        finally:
            r.close()

    def test_malformed_stale_and_wrong_session_packets_cannot_change_playback(self):
        r = DeviceRig('packet-device-check')
        r.api['Init']()
        try:
            r.apply(allow=1)
            r.wait(lambda s: s['phase'] == 'playing')
            packets = [r.packet(seq=0), r.packet(seq=r.seq+1, session='another-session'),
                       r.packet(seq=r.seq+1, music='nan'), r.packet(seq=r.seq+1, track=9),
                       r.packet(seq=r.seq+1, win=-1), r.packet(seq=r.seq+1, epoch=0),
                       r.packet(seq=r.seq+1, menu=2), r.packet(seq=r.seq+1, menu=-1),
                       r.packet(seq=r.seq+1).replace('JWN5|', 'JWN4|'),
                       r.packet(seq=r.seq+1).removesuffix('\n'), r.packet(seq=r.seq+1)+'junk',
                       r.packet(seq=r.seq+1).replace('|END', '|BROKEN')]
            for packet in packets:
                r.raw(packet)
                r.dwell(.22)
                s = r.wait(lambda s: True)
                self.assertEqual(s['seq'], str(r.seq), packet)
                self.assertEqual(s['phase'], 'playing', packet)
            r.apply(menu=1)
            r.wait(lambda s: s['phase'] == 'playing' and s['menu'] == '1')
            r.api['Stop']()
            r.wait(lambda s: s['emergency'] == '1' and s['music_stopped'] == '1' and s['ready'] == '0')
        finally:
            r.close()

    def test_bad_pcm_fails_before_music_permission_and_recovery_requires_transition(self):
        r = DeviceRig('bad-pcm-device-check')
        r.api['Init']()
        try:
            (r.folder / 'Audio/jamie_wins.wav').write_bytes(b'not a RIFF file')
            r.apply()
            failed = r.wait(lambda s: s['phase'] == 'failed')
            self.assertEqual(failed['operation'], 'validate_pcm')
            self.assertEqual(failed['music_stopped'], '1')
            self.assertEqual(failed['ready'], '0')
            r.silence('jamie_wins')
            r.apply(music=.3)
            r.wait(lambda s: s['phase'] == 'failed')
            r.apply(epoch=2, allow=1)
            r.wait(lambda s: s['phase'] == 'playing' and int(s['samples']) > 1000)
        finally:
            r.close()

    def test_bad_m4a_fails_before_music_permission_and_can_recover(self):
        r = DeviceRig('bad-compressed-device-check')
        r.api['Init']()
        try:
            (r.folder / 'Audio/mr_top_player.m4a').write_bytes(b'not an M4A file')
            r.apply()
            failed = r.wait(lambda s: s['phase'] == 'failed')
            self.assertEqual(failed['operation'], 'decode_audio')
            self.assertEqual(failed['music_stopped'], '1')
            self.assertEqual(failed['ready'], '0')
            r.silence('mr_top_player')
            r.apply(epoch=2, allow=1)
            r.wait(lambda s: s['phase'] == 'playing' and int(s['samples']) > 1000)
        finally:
            r.close()

    def test_actual_lua_coordinator_with_device_and_simulated_game_music_ack(self):
        r = DeviceRig('full-adapter-device-check')
        lua = r.lua
        lua.execute('Audio=assert(load(...))()', (PROBE / 'native_audio.lua').read_text())
        lua.execute('config=assert(load(...))()', (PROBE / 'probe_settings.lua').read_text())
        lua.execute('''
            local root=...
            logs={};gate={owned=false,phase='idle',gains={music=.45,drink=.9,win=1}}
            function gate:volumes()return self.gains end
            function gate:update(want,safe)
                if want then
                    if not self.owned then self.owned=true;self.phase='muting'
                    elseif self.phase=='muting' then self.phase='muted' end
                elseif self.owned and safe then
                    if self.phase=='restoring' then self.owned=false;self.phase='idle'
                    else self.phase='restoring' end
                end
                return self.phase=='muted'
            end
            audio=Audio.new(root,config,function(o)return o~=nil end,function(s)logs[#logs+1]=s end,gate)
            state={active=true,owner={},controller={},player='test-pawn',track='none',
                paused=false,heavy=0,wins=0,detail='silent device test'}
        ''', r.folder.as_posix())
        state, adapter, gate = lua.globals().state, lua.globals().audio, lua.globals().gate

        def tick_until(predicate, timeout=5):
            deadline = time.monotonic() + timeout
            adapter.update(adapter, state, time.monotonic())  # one gameplay/slider event
            while time.monotonic() < deadline:
                adapter.service(adapter, time.monotonic())
                if predicate():
                    return
                time.sleep(.05)
            self.fail(f'Adapter timeout; phase={adapter.phase}; logs={list(lua.globals().logs.values())}; status={r.status()}; evidence={r.folder}')

        try:
            adapter.update(adapter, state, time.monotonic())
            self.assertIsNone(adapter.api)
            state.track = 'armed'
            tick_until(lambda: adapter.phase == 'playing' and adapter.progress)
            before_menu = int(r.status()['music_frames'])
            state.paused = True
            tick_until(lambda: adapter.phase == 'playing' and r.status().get('menu_mix') == '1.000000')
            self.assertGreater(int(r.status()['music_frames']), before_menu)
            self.assertTrue(gate.owned)
            state.paused = False
            tick_until(lambda: adapter.phase == 'playing' and r.status().get('menu_mix') == '0.000000')
            state.inMenu = True
            tick_until(lambda: r.status().get('menu_mix') == '1.000000')
            state.inMenu = False
            tick_until(lambda: r.status().get('menu_mix') == '0.000000')
            state.track, state.heavy, state.wins = 'drunk', 1, 1
            tick_until(lambda: adapter.phase == 'playing' and adapter.track == 'drunk' and r.status().get('drink_playing') == '1')
            sequence = adapter.sequence
            for _ in range(8):
                adapter.service(adapter, time.monotonic())
                time.sleep(.05)
            self.assertEqual(adapter.sequence, sequence)
            gate.gains.music = .1
            tick_until(lambda: abs(float(r.status().get('music_gain', '0'))-.1) < .0001)
            self.assertEqual(adapter.sequence, sequence+1)
            state.active = False
            tick_until(lambda: adapter.isStopped(adapter, time.monotonic()))
            self.assertFalse(gate.owned)
            r.seq = adapter.sequence
            self.assertEqual(r.wait(lambda s: True)['music_stopped'], '1')
        finally:
            r.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)

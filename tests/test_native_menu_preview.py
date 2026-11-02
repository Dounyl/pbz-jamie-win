"""Compare the shipping C mixer with the audition's independent FFmpeg filter.

Renders offline only. Does not load PBZ or open an audio device.
"""
from array import array
import json
import math
import os
from pathlib import Path
import subprocess
import uuid
import wave

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'probes/JamieWinNativeAudioTest/Native'
FFMPEG = ROOT / '.local/cache/audio-tools/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe'
FOLDER = ROOT / '.local/native-audio-test' / ('menu-preview-check-' + uuid.uuid4().hex)
FOLDER.mkdir(parents=True)
env = os.environ.copy()
env['ZIG_GLOBAL_CACHE_DIR'] = str(ROOT / '.local/cache/zig-global')
env['ZIG_LOCAL_CACHE_DIR'] = str(ROOT / '.local/cache/zig-local')
exe = FOLDER / 'render.exe'
subprocess.run([str(ROOT / '.local/cache/native-build/ziglang/zig.exe'), 'cc', '-target',
                'x86_64-windows-gnu', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                str(ROOT / 'tests/native_menu_preview.c'), str(NATIVE / 'mixer.c'),
                str(NATIVE / 'menu_filter.c'), '-o', str(exe)], env=env, check=True)


def ffmpeg(*args):
    return subprocess.run([str(FFMPEG), '-hide_banner', '-loglevel', 'error', '-nostdin',
                           *map(str, args)], stdout=subprocess.PIPE, check=True).stdout


dry = ffmpeg('-ss', 45, '-i', ROOT / 'resources/audio/mandarin_duck_play.mp3', '-t', 24,
             '-ar', 48000, '-ac', 2, '-f', 's16le', '-c:a', 'pcm_s16le', 'pipe:1')
(FOLDER / 'dry.raw').write_bytes(dry)
subprocess.run([str(exe), str(FOLDER / 'dry.raw'), str(FOLDER / 'native.raw')], check=True)
effect = ','.join(['lowpass=f=1200:p=2:t=q:w=0.70710678:r=f64'] * 2)
wet = ffmpeg('-f', 's16le', '-ar', 48000, '-ac', 2, '-i', FOLDER / 'dry.raw',
             '-af', effect, '-f', 'f64le', '-c:a', 'pcm_f64le', 'pipe:1')
source, filtered, actual = array('h'), array('d'), array('h')
source.frombytes(dry)
filtered.frombytes(wet)
actual.frombytes((FOLDER / 'native.raw').read_bytes())
assert len(actual) == len(source) == len(filtered) == 24 * 48000 * 2

maximum, squared, count = 0, 0.0, 0
for frame in range(48000, 24 * 48000):
    t = frame / 48000
    if t < 6 or t >= 16.4:
        weight = 0
    elif t < 6.4:
        weight = .5 - .5 * math.cos(math.pi * (t - 6) / .4)
    elif t < 16:
        weight = 1
    else:
        weight = .5 + .5 * math.cos(math.pi * (t - 16) / .4)
    for channel in range(2):
        i = frame * 2 + channel
        expected = .45 * ((1 - weight) * source[i] + weight * .9 * filtered[i] * 32768)
        error = abs(actual[i] - expected)
        maximum = max(maximum, error)
        squared += error * error
        count += 1
assert maximum < 2, f'Native filter differs from the audition recipe: {maximum} PCM units'
assert max(abs(value) for value in actual) < 32767
wav_path = FOLDER / 'native-menu-preview.wav'
with wave.open(str(wav_path), 'wb') as output:
    output.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
    output.writeframes(actual.tobytes())
report = {
    'duration_seconds': 24, 'entry_seconds': 6, 'exit_seconds': 16, 'transition_seconds': .4,
    'filter': effect, 'reference': 'FFmpeg on the same 48 kHz PCM source as the packaged music',
    'maximum_error_pcm16': maximum, 'rms_error_pcm16': math.sqrt(squared / count),
    'music_frames_advanced': 24 * 48000, 'clipped_output_samples': 0,
    'native_render': str(wav_path),
}
(FOLDER / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))

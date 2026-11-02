"""Decode the shipped original M4A/MP3 and compare with independent FFmpeg PCM.

Checks resampling, duration, waveform, bounded allocation and bad-file rejection.
Does not open an audio output device or launch the game.
"""
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'probes/JamieWinNativeAudioTest/Native'
FFMPEG = ROOT / '.local/cache/audio-tools/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe'
FOLDER = ROOT / '.local/native-audio-test' / ('decode-check-' + uuid.uuid4().hex)
FOLDER.mkdir(parents=True)
env = os.environ.copy()
env['ZIG_GLOBAL_CACHE_DIR'] = str(ROOT / '.local/cache/zig-global')
env['ZIG_LOCAL_CACHE_DIR'] = str(ROOT / '.local/cache/zig-local')
exe = FOLDER / 'decode.exe'
subprocess.run([str(ROOT / '.local/cache/native-build/ziglang/zig.exe'), 'cc', '-target',
                'x86_64-windows-gnu', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-municode',
                str(ROOT / 'tests/native_audio_decode.c'), str(NATIVE / 'media_decode.c'),
                '-lmfplat', '-lmfreadwrite', '-lmfuuid', '-lole32', '-o', str(exe)], env=env, check=True)


def decode(source, name, limit=64 * 1024 * 1024):
    return subprocess.run([str(exe), str(source), str(FOLDER / (name + '.raw')), str(limit)],
                          capture_output=True, text=True, timeout=15)


reports = []
for name in ('mr_top_player.m4a', 'mandarin_duck_play.mp3'):
    original = ROOT / 'resources/audio' / name
    shipped = ROOT / '.local/native-audio-build' / name
    digest = hashlib.sha256(shipped.read_bytes()).hexdigest()
    assert digest == hashlib.sha256(original.read_bytes()).hexdigest(), 'Source audio was re-encoded'
    # A Unicode directory also exercises the Windows wide-character path throughout decoding.
    unicode_source = FOLDER / ('音频-' + name)
    unicode_source.write_bytes(shipped.read_bytes())
    result = decode(unicode_source, name)
    assert result.returncode == 0, result.stderr
    info = json.loads(result.stdout)
    actual = array('h')
    actual.frombytes((FOLDER / (name + '.raw')).read_bytes())
    reference = array('h')
    reference.frombytes(subprocess.run([str(FFMPEG), '-hide_banner', '-loglevel', 'error', '-nostdin',
        '-i', str(original), '-ar', '48000', '-ac', '2', '-f', 's16le', '-c:a', 'pcm_s16le', 'pipe:1'],
        stdout=subprocess.PIPE, check=True).stdout)
    assert len(actual) == info['frames'] * 2
    duration_error = abs(len(actual) - len(reference)) / 96000
    assert duration_error < .1, f'{name}: sample rate/duration mismatch: {duration_error}'
    # Codec priming/padding can differ between decoders; compare a real music window after aligning it.
    start, stride, count = 45 * 48000, 97, 512
    expected = [reference[(start + i * stride) * 2] for i in range(count)]
    expected_energy = sum(value * value for value in expected)
    best = (-1.0, 0, 0.0)
    for offset in range(-4096, 4097):
        observed = [actual[(start + offset + i * stride) * 2] for i in range(count)]
        energy = sum(value * value for value in observed)
        dot = sum(a * b for a, b in zip(expected, observed))
        correlation = dot / math.sqrt(expected_energy * energy) if energy else 0
        if correlation > best[0]:
            best = (correlation, offset, math.sqrt(energy / expected_energy))
    correlation, offset, amplitude = best
    assert correlation > .98, f'{name}: decoded waveform mismatch: {best}'
    assert .95 < amplitude < 1.05, f'{name}: unexpected decoder gain: {amplitude}'
    assert info['elapsed_ms'] < 8000
    reports.append(dict(name=name, source_sha256=digest, source_bytes=shipped.stat().st_size,
                        **info, duration_error_seconds=duration_error, correlation=correlation,
                        alignment_frames=offset, decoder_amplitude_ratio=amplitude))
    limited = decode(unicode_source, 'over-limit', limit=4096)
    assert limited.returncode == 1, f'Decoder must reject audio exceeding the PCM limit: {limited.stderr}'

for name, payload in [('bad.m4a', b'not a media file'), ('bad.mp3', b'ID3\x00'), ('empty.m4a', b'')]:
    source = FOLDER / name
    source.write_bytes(payload)
    result = decode(source, name)
    assert result.returncode == 1, f'Decoder accepted malformed audio: {name}'
assert decode(FOLDER / 'missing.m4a', 'missing').returncode == 1
report = dict(tracks=reports, malformed_and_missing_files_rejected=True, pcm_limit_enforced=True,
              source_files_unchanged=True, evidence=str(FOLDER))
(FOLDER / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))

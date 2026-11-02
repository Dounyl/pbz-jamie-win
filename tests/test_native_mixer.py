"""Compile and inspect actual PCM output; this test executable is never shipped."""
from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
env = os.environ.copy()
env['ZIG_GLOBAL_CACHE_DIR'] = str(ROOT / '.local/cache/zig-global')
env['ZIG_LOCAL_CACHE_DIR'] = str(ROOT / '.local/cache/zig-local')
exe = ROOT / '.local/native-audio-build/mixer-test.exe'
exe.parent.mkdir(parents=True, exist_ok=True)
subprocess.run([str(ROOT / '.local/cache/native-build/ziglang/zig.exe'), 'cc', '-target', 'x86_64-windows-gnu',
                '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', str(ROOT / 'tests/native_mixer_test.c'),
                str(ROOT / 'probes/JamieWinNativeAudioTest/Native/mixer.c'),
                str(ROOT / 'probes/JamieWinNativeAudioTest/Native/menu_filter.c'), '-o', str(exe)], env=env, check=True)
subprocess.run([str(exe)], check=True)

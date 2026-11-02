# 开发与构建

当前版本为 **1.1.0**，音频在游戏进程内播放。源码集中在 `probes/JamieWinNativeAudioTest/`，安装 ID 为 `JamieWinNativeAudioTest`。

## 源码结构

| 文件 | 职责 |
| --- | --- |
| `Scripts/main.lua` | 游戏线程调度、日志与 F10 停用 |
| `Scripts/core.lua`、`weapon.lua`、`gameplay.lua` | 醉态、当前持剑、菜单和玩家状态检测 |
| `Scripts/settings.lua` | 采样间隔、处决语音延迟和游戏类名 |
| `Scripts/probe_settings.lua` | 运行时版本与状态超时 |
| `Scripts/executions.lua` | 处决开始检测、去重、延迟和取消 |
| `Scripts/game_audio.lua` | 读取游戏音量设置，接管与恢复原配乐 |
| `Scripts/native_audio.lua` | Lua 与原生音频层的状态协调 |
| `Native/audio.c` | Windows 音频设备、命令、心跳与状态输出 |
| `Native/mixer.c`、`menu_filter.c` | 音乐循环、语音叠加、音量和菜单低通滤波 |
| `Native/media_decode.c` | Windows Media Foundation 音频解码 |
| `mod.json` | 安装 ID、显示名称、版本与发布渠道 |

## 构建依赖与命令

在 Windows x64 上使用 Python 3.13，项目缓存中的依赖与 GitHub Actions 一致：

```powershell
python -m pip install --only-binary=:all: --target .local/cache/native-build ziglang==0.13.0
python -m pip install --only-binary=:all: --target .local/cache/audio-tools imageio-ffmpeg==0.7.0
python -m pip install --only-binary=:all: --target .local/cache/testdeps lupa==2.8
& ./tools/build-native-audio-test.ps1
```

构建脚本支持用 `-Compiler` 和 `-FFmpeg` 指定工具路径。DLL 与处理后的资源输出到 `.local/native-audio-build/`。

两首背景音乐直接从 `resources/audio/` 复制原始 M4A / MP3，运行时解码为 48 kHz、双声道 PCM16；构建时仅将两段语音转换为相同 PCM 格式。FFmpeg 还用于离线参考检查。

## 当前播放规则

游戏音量滑块控制各通道。音乐基础增益为总音量乘音乐音量再乘 `0.45`，《Mr.Top.Player》另乘 `1.44`；四酒语音为总音量乘对话音量再乘 `0.9`，Jamie wins 为总音量乘对话音量。语音叠加不改变背景音乐的音量或播放进度。

菜单效果使用两级 1200 Hz 低通滤波，在 0.4 秒内渐变。菜单期间音乐持续播放，语音暂停；退出菜单后恢复。清醒收剑时停止 Mod 音乐并恢复游戏原配乐，已触发的语音可以继续；死亡、无玩家、标题界面或 F10 停用时停止全部 Mod 音频并恢复原配乐。

处决只接受醉剑的 `GA_Hun_BEx_ChiZheCanJian_M_01_C` 和 `_M_02_C` 执行者能力。在 `Play Execution` 回调后，要求成对处决时间线已播放、执行者为当前本地玩家、目标是另一个存活角色。同一次能力只记录一次开始事件，`settings.lua` 中的 `ExecutionVoiceDelayMs = 2000` 控制语音延迟。

已经确认的处决不会因提前结束或目标在等待期间死亡而丢失语音；玩家死亡、切图、更换玩家或 F10 停用会取消待播事件。普通重击、可处决提示和处决结束不会新建语音请求。

## 回归验证

先构建，再在项目根目录运行：

```powershell
python tests/test_native_audio_probe.py
python tests/test_native_menu_detection.py
python tests/test_lua.py
python tests/test_native_mixer.py
python tests/test_native_audio_decode.py
python tests/test_native_menu_preview.py
python tests/test_native_audio_device.py
```

Lua 检查覆盖状态转换、持剑检测、音量接管与恢复、处决时机、菜单和失败恢复；C 检查覆盖实际混音样本、原始音频解码及菜单滤波的离线对照。设备检查在独立测试进程中仅播放生成的静音数据，不启动或操作游戏。

生成的测试记录位于 `.local/native-audio-test/`。游戏内的听感和动作时机需要玩家操作验证，离线与设备检查不代替实机验收。

## 打包与发布

```powershell
& ./tools/package-native-audio-test.ps1
```

脚本校验 `mod.json`、Lua 和 DLL 的版本一致性，重新构建并生成 `.local/releases/时间戳/JamieWin-版本.zip` 与 SHA256 文件。包内包含 9 个 Lua 脚本、4 份音频、1 个 DLL、元数据、启用标记、空运行目录占位文件和安装说明，共 18 个文件。

安装使用 UEMM，文件部署到 `platform/steam/ue4ss/Mods/JamieWinNativeAudioTest/`。构建、测试和打包工具只写项目的 `.local/`，不安装或修改游戏目录。

GitHub 发布流程见 [GitHub Release 打包](github-release.md)。排查运行问题时收集 Mod 下 `runtime/native-audio-test.log`、`native-output.log`、`native-status.txt` 以及 `platform/steam/ue4ss/UE4SS.log`。

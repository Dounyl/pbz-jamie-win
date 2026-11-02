# JamieWin · 影之刃零醉剑音频 Mod

清醒持醉剑时播放《Mr.Top.Player》，微醺或大醉时切换《鸳鸯戏》，并配上杰米四酒日语音效和处决开始时的「Jamie wins」。

当前版本是 **1.0.0 正式版**，沿用 `JamieWinNativeAudioTest` 安装目录，方便从已测试的版本更新。音频由一个 DLL 在游戏进程内播放，无需外部播放器。

**验证状态：** 2026-11-02，用户确认最新 0.5.0 候选包测试通过，现升级为 1.0.0 正式版。沿用已验收的音量跟随、原配乐接管、语音、混音和菜单实时滤波功能；本次仅更新版本与发布说明。

## 播放规则

| 游戏中的状态或动作 | 播放内容 |
| --- | --- |
| 清醒且实际手持醉剑 | 循环《Mr.Top.Player》；只放在背包里不触发 |
| 微醺或大醉 | 循环《鸳鸯戏》 |
| 微醺与大醉互换 | 同一首继续，不重头播放 |
| 每次新进入大醉 | 四酒日语音效一次 |
| 本地玩家发动醉剑处决，目标仍存活 | 动作开始时播放一次「Jamie wins」 |
| 恢复清醒仍持醉剑 | 切回《Mr.Top.Player》 |
| 清醒收剑／换武器 | 停止 Mod 音乐，恢复游戏原配乐 |
| 死亡、无玩家、标题界面 | 停止音乐和语音，恢复原配乐 |
| 打开暂停、设置或系统菜单 | 音乐继续播放，0.4 秒内逐渐变闷；语音暂存当前位置 |
| 退出菜单继续游戏 | 音乐在当前进度上用 0.4 秒恢复清晰；语音接续，待播语音触发一次 |
| F10 | 停声并恢复原配乐后停用本次 Mod；完全重启游戏后再次启用 |

切换玩家或载入已经处于大醉的角色时，不补播历史四酒事件。只修改听到的音频，不修改角色数值、战斗逻辑和存档。

菜单效果沿用已确认的试听：两级 1200 Hz 低通、滤波分支额外 90% 音量、0.4 秒平滑混合。反复打开和关闭菜单、菜单中调整音量都保持歌曲进度；回到标题界面仍停止音乐。

## 音量

直接使用游戏音量设置，无需编辑配置文件：

- Mod 音乐跟随「总音量 × 音乐音量」，内部平衡为 45%。
- 四酒和处决语音跟随「总音量 × 对话／语音音量」，内部平衡分别为 90% 和 100%。
- 语音期间，Mod 音乐从 45% 暂时降至 20%，结束后平滑恢复。

游戏音乐音量设为零只关闭 Mod 音乐；对话音量设为零关闭两种语音；总音量设为零关闭全部。调整音量不会重播当前曲目，也不改变 Windows 设备音量。

Mod 音乐开始前会确认原配乐静音；停止后确认设备已无 Mod 音乐，再恢复游戏最新的音乐音量偏好。不保存或覆盖游戏设置。

## 更新与安装

目标环境：Windows x64，PBZ Steam build `26266538`，适配 PBZ 的 UE4SS `v3.0.1-1195-g1ceefac8`。其他版本尚未验证。

1. 完全退出游戏。
2. 在现有 Mod 管理器中，用 `JamieWin-1.0.0.zip` 更新现有 Mod，保留已安装的兼容 UE4SS。显示名称为 **JamieWin**，版本单独显示为 **1.0.0**；安装目录仍为 `JamieWinNativeAudioTest`。
3. 同时只启用一个 JamieWin 版本；旧的 `JamieWin` 外部播放器版保持停用。
4. 从 Steam 正常启动游戏。日志应出现 `BOOT 1.0.0-stable`。进入存档并满足播放条件后才加载音频 DLL。

包内只有 Mod Lua、一个 DLL、四份 WAV 和说明，不包含播放器 EXE、加载器或转换工具。目录是：

```text
platform/steam/ue4ss/Mods/JamieWinNativeAudioTest/
├─ Scripts/
├─ Native/JamieWinAudio.dll
├─ Audio/                         两首音乐和两种语音
├─ runtime/
├─ mod.json                       名称、版本、安装 ID 和渠道
└─ enabled.txt
```

更新、停用和卸载均先退出游戏，再用管理器操作同一个 Mod。DLL 随游戏退出而卸载，不支持运行中覆盖或热重载。

版本以包内 `mod.json` 为准。源码中的该文件是打包元数据，脚本从中读取名称和版本，并校验 Lua、DLL 内部版本一致。UE MM 1.4.1 的本地导入尚不读取此文件，因此 ZIP 末尾保留版本用于填充其独立的 Version 字段；构建时间放在包外的归档目录中，不加入 Mod 显示名称。

## 功能检查

依次检查持剑、微醺、大醉、反复进入大醉、醉剑处决、菜单进出、清醒收剑、死亡和 F10。确认四酒不重复、处决在动作开始时出声、语音期间背景音乐降低，以及停止后原配乐恢复。

播放任一首音乐时进入设置菜单，停留至少 10 秒再退出：菜单中应持续变闷播放，退出后听到歌曲更后面的进度并恢复清晰。快速开关菜单几次、切换设置子页也不应重播或突然切换音色。标题、死亡和 F10 仍应停声。

播放中分别调整游戏的总音量、音乐音量和对话音量，包含设置为零再恢复；调整后曲目应从原位置接续。Mod 播放期间修改音乐音量，收剑后原配乐应采用修改后的值。

异常时保留本 Mod `runtime/native-audio-test.log`、`native-output.log` 和 `native-status.txt`，以及 `ue4ss/UE4SS.log`。`DEVICE_CLOCK_ADVANCED` 只表示设备计数推进，是否真正可听仍以用户为准。

## 源码与构建

当前实现位于 `probes/JamieWinNativeAudioTest/`，共享原有 `core.lua`、`weapon.lua` 和 `settings.lua`。在项目根目录执行：

```powershell
& ./tools/build-native-audio-test.ps1
python tests/test_native_audio_probe.py
python tests/test_native_menu_detection.py
python tests/test_lua.py
python tests/test_native_mixer.py
python tests/test_native_menu_preview.py
python tests/test_native_audio_device.py
& ./tools/package-native-audio-test.ps1
```

构建依赖项目缓存中的 Zig 0.13.0 和 FFmpeg，Lua 检查使用 `.local/cache/testdeps` 中的 Lupa。构建脚本支持显式传入编译器和 FFmpeg 路径。产物仅写入 `.local/`；测试使用独立进程中的静音数据，不安装或操作游戏。

实现、边界和逐轮实测证据见 [进程内音频记录](docs/native-audio-probe.md)。旧 `mods/JamieWin` / `src/AudioHost.cs` 保留供比对，历史使用说明见 [旧外部播放器版](docs/legacy-external-player.md)；不要将旧版配置或启动步骤用于当前包。

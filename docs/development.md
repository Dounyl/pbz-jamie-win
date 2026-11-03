# 开发与构建

当前源码为 **0.0.20261103 事件驱动测试版**（运行时 `0.0.20261103-event-test`），音频在游戏进程内播放。源码集中在 `probes/JamieWinNativeAudioTest/`，安装 ID 为 `JamieWinNativeAudioTest`。离线与设备检查不代表新增钩子的实机覆盖已经通过。

## 源码结构

| 文件 | 职责 |
| --- | --- |
| `Scripts/main.lua` | 合并游戏事件、独立音频维护、日志与 F10 停用 |
| `Scripts/game_events.lua` | 状态变化钩子、动态蓝图类注册、切图和对象生命周期 |
| `Scripts/core.lua`、`weapon.lua`、`gameplay.lua` | 醉态、当前持剑、菜单和玩家状态检测 |
| `Scripts/settings.lua` | 音频维护间隔、处决语音延迟和游戏类名 |
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

### 事件驱动与音频维护

首次启动读取一次状态，之后只在游戏事件发生时读取。事件回调通过 `ExecuteInGameThread` 合并到下一次游戏线程执行，读取事件处理后的实际状态；执行过程中收到的新事件保留到下一帧。钩子不修改参数，也不覆盖引擎返回值。

| 状态 | 事件入口 |
| --- | --- |
| 菜单 | CommonUI 的 `BP_OnActivated` / `BP_OnDeactivated`、根控件 Construct / Destruct、`SetGamePaused` |
| 持剑与换武器 | CharacterWeaponsComponent 的 SetArmed / SetCurrentWeapon / SetSlotWeapon 等；拔收剑能力和动作蓝图的状态完成回调 |
| 醉态 | 醉剑被动能力的 IntoZuiStep / ExitZuiStep、Added / Removed、饮酒反馈；对应 GameplayCue 的进入、持续状态初始化与移除 |
| 玩家生命周期 | 本地玩家的开始、占有、失去控制、结束、死亡、生命跨零与复活回调；LoadMap 前后钩子 |
| 音量 | PBZSettingsShared 的总音量、音乐和对话音量 setter |
| 处决 | 原有 Play Execution 开始钩子和一次性 2 秒延迟回调 |

注册依据为 build `26266538` 的反射导出。UE4SS 的 [RegisterHook](https://docs.ue4ss.com/lua-api/global-functions/registerhook.html) 只覆盖实际调用的 UFunction；不能把原生 C++ 直接调用 setter 当成已覆盖，因此同时监听动作与状态蓝图回调。动态蓝图必须挂到实际派生类的函数，选择每个函数名最派生的实现；不挂 Tick、动画 Tick 或委托签名。`NotifyOnNewObject` 回调只排队对象，后续在游戏线程安装钩子。已有菜单仅在初始化或控制器更换时发现，后续创建事件直接加入缓存。

`AudioServiceMs = 200` 仅负责 DLL 心跳、状态文件和静音/恢复握手，使用最近事件的不可变快照；稳定播放时不读角色、菜单、滑块或世界子系统。准备、停止和故障恢复期间仍需确认游戏原配乐的 RTPC。没有固定频率的游戏状态查询或静默降级轮询。

2026-11-03 读档崩溃转储显示：`PBZ.exe+0x619C9F0` 读取空的脚本指针，调用链经过 `PBZ.exe+0x62B3595` 和 `UE4SS.dll+0xB14565`。反射导出中角色的 Respawn、ReceiveEndPlay、Health Post Func 使用 Puerts 桥接入口 `PBZ.exe+0x62B3490`，且崩溃前被注册为原生钩子。针对这条路径，事件注册现在读取 `GetFunctionFlags()`，跳过资产包内带 `FUNC_Native` 的函数并记录 `EVENT_SKIP native asset bridge`；跳过派生覆盖时不额外注册同名父类函数。其他函数按实际 flags 选择原生 post 或脚本回调，不能只凭 `/Script/` 路径判断。`EVENT_MODE` 中的 `native_asset_bridges=skipped; hook_dispatch=flags` 标识此修复。离线测试覆盖读档后出现混合原生／蓝图派生类，以及 `/Script/` 中的非原生控件事件；同存档读档和死亡／复活等生命周期覆盖仍待实机复测。

切图前后即使合并到同一帧也会清除待播处决并发送停止状态。死亡/失去控制/EndPlay 取消旧事件；F10 关闭事件处理并等待音频停止和原配乐恢复。安装或观察失败会记录日志并停止播放，后续游戏事件可重新尝试注册或读取。

回归检查覆盖无事件时 3000 次音频维护不增加游戏采样、同帧合并、处理中新事件、动态菜单覆盖、派生类注册、无关角色过滤、生命跨零、切图、停止及音量快照。反射符号存在与这些模拟检查均不能替代实机回调覆盖：需要按 README 的场景复测，并结合 `EVENT_MODE`、`EVENT_HOOK`、`EVENT_SEEN`、`EVENT_ERROR` 和 `GAMEPLAY` 日志检查。

### 运行检查

先构建，再在项目根目录运行：

```powershell
python tests/test_native_audio_probe.py
python tests/test_native_menu_detection.py
python tests/test_game_events.py
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

脚本校验 `mod.json`、Lua 和 DLL 的版本一致性，重新构建并生成 `.local/releases/时间戳/JamieWin-版本.zip` 与 SHA256 文件。包内包含 10 个 Lua 脚本、4 份音频、1 个 DLL、元数据、启用标记、空运行目录占位文件和安装说明，共 19 个文件。事件版元数据的 channel 为 `event-test`。

安装使用 UEMM，文件部署到 `platform/steam/ue4ss/Mods/JamieWinNativeAudioTest/`。构建、测试和打包工具只写项目的 `.local/`，不安装或修改游戏目录。

GitHub 发布流程见 [GitHub Release 打包](github-release.md)。排查运行问题时收集 Mod 下 `runtime/native-audio-test.log`、`native-output.log`、`native-status.txt` 以及 `platform/steam/ue4ss/UE4SS.log`。

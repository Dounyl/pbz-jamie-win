# JamieWin 开发与技术说明

面向玩家的功能介绍、安装、设置与卸载步骤见 [README](../README.md)。本文保留实现细节、开发流程与既有验证记录。

**当前使用 1.0.0 进程内音频正式版，已由用户确认测试通过。** 构建入口为 `tools/package-native-audio-test.ps1`，
当前源码在 `probes/JamieWinNativeAudioTest/`。新增混音、游戏音量跟随及设备验证见
[进程内音频记录](native-audio-probe.md)。本文以下外部播放器、`audio.json` 和自动启动流程是历史方案，不适用于当前包。

## 适配环境

目标版本：Steam build `26266538`。使用已适配的 UE4SS `v3.0.1-1195-g1ceefac8`。

游戏侧 Lua 脚本位于 `mods/JamieWin/Scripts/`，独立音频播放器位于 `src/AudioHost.cs`。游戏状态、持剑状态与处决事件决定播放内容，当前播放规则见 README。

## 游戏背景音乐如何切换

使用游戏 `PBZSoundFXSubsystem.SetAudioVolume(MusicVolume, ...)` 临时控制音乐通道。游戏的配乐逻辑继续运行，音量偏好不写入存档，也不调用 `SaveSettings`。

1. 播放器先加载并解码音频，确认目标曲目可播放后向游戏申请接管。
2. Mod 从游戏配置加载音乐 RTPC，读取原音量并将音乐通道设为零；在后续游戏帧回读确认，等待音频线程处理指令。
3. 播放器收到本次请求对应的确认后才开始播放。
4. 不再需要 Mod 音乐时，先停止 Mod 音乐，再确认已停止，游戏才恢复音量。清醒但仍手持醉剑时，改为播放《Mr.Top.Player》。
5. 播放器崩溃或退出：游戏的心跳租约到期后恢复原乐。游戏无响应：播放器在约 1.2 秒内停止 Mod 音乐。

未能确认原乐静音时，不启动 Mod 背景音乐。播放期间用户修改游戏音乐设置，恢复时采用最新偏好。两首 Mod 背景音乐切换时先停止前一首；微醺与大醉互相切换时，《鸳鸯戏》的播放位置不重置。

音量回读会等待后续帧，因为 [Wwise 的查询结果可能晚于音频指令生效](https://github.com/audiokinetic/WwiseIncludes/blob/master/SDK/include/AK/SoundEngine/Common/AkQueryParameters.h)。

## 本地配置与资源

配置位于项目根目录的 `audio.json`，其中包含：

| 字段 | 用途 |
| --- | --- |
| `Bridge` | 游戏侧 `ue4ss/Mods/JamieWin/runtime/bridge.txt` 的路径，必须与实际安装位置一致 |
| `Music` | 微醺、大醉时的背景音乐 |
| `ArmedMusic` | 清醒且手持醉剑时的背景音乐 |
| `Drink` | 新进入大醉时的音效 |
| `Win` | 醉剑处决开始时的语音 |
| `Runtime` | 播放器运行文件与日志目录，默认 `.local/runtime` |
| `MusicVolume`、`DrinkVolume`、`WinVolume`、`DuckVolume` | 背景音乐、四酒音效、处决语音和语音期间背景音乐的音量，范围均为 `0` 到 `1` |

相对路径以 `audio.json` 所在目录为基准。默认背景音乐音量为 45%，音效与胜利语音播放时暂时降至 20%。修改配置后重启播放器即可。

四个成品音频统一放在 `resources/audio/`，使用小写英文和下划线命名：

| 内容 | 文件名 |
| --- | --- |
| 鸳鸯戏 | `mandarin_duck_play.mp3` |
| Mr.Top.Player | `mr_top_player.m4a` |
| 杰米四酒（日语） | `jamie_drink4_ja.wav` |
| Jamie wins | `jamie_wins.wav` |

下载素材、重复格式、提取记录、缓存、构建产物和本地运行日志都放在 `.local/`，该目录由 Git 忽略。

## 安装与启动脚本

### 加载器安装工具

`tools/install-loader.ps1` 用于安装本地已准备并验证的加载器包，不负责下载。它要求包位于 `.local/cache/loader-1195/`，包含 `dwmapi.dll` 和 `ue4ss/UE4SS.dll`。该缓存目录不随仓库分发。

关闭游戏后，在项目根目录运行，按实际情况修改游戏路径：

```powershell
.\tools\install-loader.ps1 -GameRoot "D:\SteamLibrary\steamapps\common\PBZ"
```

脚本检查 `platform/steam/PBZ.exe`，拒绝覆盖已有的 `dwmapi.dll` 或 `ue4ss` 目录，仅启用包内的 Keybinds，并将版本、安装路径与文件哈希写入 `.local/cache/loader-install.json`。已有加载器时，不要为重复安装而直接删除共用文件。

### Mod 安装与音频进程

- `tools/install-mod.ps1 -GameRoot <游戏目录>` 检查加载器是否存在，将 Lua 脚本复制到独立的 `platform/steam/ue4ss/Mods/JamieWin` 目录，并创建 `runtime/` 与 `enabled.txt`。它不会自动修改 `audio.json` 的 `Bridge` 路径。
- `Start-JamieWin.ps1` 在播放器不存在时调用构建脚本，然后启动后台播放器；当前播放器按桥接文件路径使用互斥锁防止重复实例。
- `Stop-JamieWin.ps1` 请求播放器关闭 Mod 音频并通知游戏恢复配乐。
- 修改 Lua 后需要重新安装脚本并完全重启游戏；修改 C# 后需要重新构建并重启播放器。

Mod 不修改游戏数值、战斗逻辑和存档。游戏接口探测脚本及导出信息仅保留本地，不随音频 Mod 公开分发。

源码开发时，在根目录 `audio.json` 中将 `Bridge` 改为实际安装目录下的 `platform/steam/ue4ss/Mods/JamieWin/runtime/bridge.txt`，保留其余字段。先运行 `Start-JamieWin.ps1`，再从 Steam 启动游戏；停止使用时运行 `Stop-JamieWin.ps1`。开发配置依赖工作区中的播放器与音频，请保留源码目录。不要同时使用开发播放器和游戏目录内的候选版播放器。

## 开发与验证

在项目根目录运行：

```powershell
.\tools\build.ps1
.\tools\test.ps1
python .\tests\test_audio_host.py
```

编译使用 Windows 自带 .NET Framework 的 C# 编译器，产物写入 `.local/dist/`，播放器没有额外 Python 依赖。Lua 测试依赖 Python 和 Lupa/Lua 5.4；测试脚本会将项目 `.local/cache/testdeps` 加入模块搜索路径，该缓存不随仓库分发，需自行准备依赖。

`tools/test.ps1` 会重新构建播放器，运行 Lua 状态机测试、C# 协议测试，以及四个音频文件的无播放解码检查。`tests/test_audio_host.py` 使用模拟桥接消息与静音配置检查独立播放器，不代替实机验收。

### 日志位置

- 播放器日志：`.local/runtime/audio.log`。
- 音频解码检查：`.local/runtime/audio-check.log`。
- 游戏侧日志：`<游戏目录>/platform/steam/ue4ss/Mods/JamieWin/runtime/game.log`。

### 既有验证记录

以下记录从原 README 迁入，反映此前的验证结果，不代表后续每次改动都已完成实机复测：

- 已从本机 SDK 和实机日志确认清醒、微醺、大醉之间的转换。
- 当时的三段本地音频已通过 Windows 原生播放器解码检查。
- Lua 状态机、双向切换协议和独立播放器的静音集成测试已通过。
- 杰米四酒音效和醉剑处决的 Jamie wins 已由用户实机确认。
- 音乐切换已通过实机日志验证：`BUS_Mus_Volume` 从 `1` 降至 `0` 后才开始播放，结束播放时先停歌再恢复到 `1`；微醺升至大醉时歌曲连续播放。
- 用户已实机确认当时的三段音频和背景音乐切换均有效。随后按反馈调低歌曲音量，并将处决语音提前至动作开始；原记录注明时机调整需下次启动加载。

2026-11-02 的 v0.7 实机日志已确认：13:58:59 当前武器为 `Weapon_Hun_ChiZheZuiJian` 且 `armed=true` 时静音原乐并播放《Mr.Top.Player》；13:59:09 收刀时先停歌，再确认原乐音量恢复为 `1`。两首歌互切、持剑/醉酒状态优先级、去重和异常恢复通过 9 项 Lua 测试、20 项协议检查与真实播放器静音集成测试；两首歌互切尚未收到用户实机反馈。

### 0.8 独立模组候选包

面向玩家的分发方向改为独立 Mod 包，UE4SS 作为公共前置由管理器安装。已核对 [UE MM 1.4.1](https://github.com/KintaroModding/uemodmanager/releases) 文档：支持 PBZ 的 `platform/steam` 路径，并将包含 `Scripts/main.lua` 的 UE4SS 模组作为整个目录部署。JamieWin 的管理器导入、停用、更新、卸载和旧安装迁移尚未实测。

构建播放器后运行 `tools/package-portable.ps1`，生成 `JamieWin-0.8.0-ModOnly-*.zip` 和 `JamieWin-0.8.0-Full-*.zip`。两者均以 `platform/steam` 为游戏根目录下的相对路径；ModOnly 仅带 JamieWin，Full 额外包含经过校验的加载器，仅供未安装 UE4SS 的首次安装使用。

播放器、音频、脚本和相对路径配置集中到 `ue4ss/Mods/JamieWin`。`autostart.lua` 请求游戏启动 `Player/JamieWin.Audio.exe`；播放器默认读取模组根目录的 `audio.json`，通过 `WatchGame=true` 和 `GameExecutable=../../../PBZ.exe` 绑定具体游戏进程，随其退出。游戏内 `LaunchURL` 自动启动仍需实机验证，不能把本地测试结果当成完整安装验收。

2026-11-02 的本地验证已通过 10 项 Lua 测试、20 项协议检查、四段音频解码和真实播放器静音集成测试。`tests/test_portable_host.py` 使用临时目录和模拟游戏进程，验证无控制台窗口、无参数读取安装配置、中文及特殊字符路径、重复实例抑制、游戏进程退出后播放器退出，以及没有游戏时不驻留。这些测试没有验证管理器操作或真实游戏发起自动启动。

旧版 0.7 的安装器、打包入口和专用测试已归档移出工作目录。当前分发只使用 `tools/package-portable.ps1`，开发用 `Start-JamieWin.ps1`、`Stop-JamieWin.ps1` 继续保留。

## 参考

- [UE4SS 适配说明](https://github.com/KintaroModding/ue4ss/blob/release/openmods.md)
- [UE4SS Hook API](https://docs.ue4ss.com/dev/lua-api/global-functions/registerhook.html)
- [Windows MediaPlayer](https://learn.microsoft.com/en-us/dotnet/api/system.windows.media.mediaplayer)

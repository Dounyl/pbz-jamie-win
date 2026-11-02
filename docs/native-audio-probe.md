# 进程内音频测试记录

测试与正式 `mods/JamieWin` 隔离。只交付测试 ZIP，由用户安装并操作游戏。
不自动启动、操作游戏，不直接覆盖管理器部署的文件。正式版尚未迁移。

## 2026-11-02：0.2.0 实际玩法测试

安装版本日志为 `BOOT 0.2.0-native-gameplay-test`（16:12:34，香港时间）。
16:13:16 正确识别清醒持醉剑，打开 `mr_top_player.m4a`；16:13:23 识别微醺，
关闭上一首并打开 `mandarin_duck_play.mp3`。两者后端都是 ElectraPlayer，
`Play` 返回 true，但时间保持 0、`outputPlaying=false`、`envelope=0`。

首次读取实际游戏配置得到：`AkRouting=WwiseOnly; Wwise=true; AudioLink=false; AkMixer=false`。
该配置和输出观测共同指向 Unreal MediaSoundComponent 输出链路不适用；
不能再仅调整标题/玩法触发、音量或将 `IsPlaying=true` 当作成功。
用户在 16:13:26 暂停、16:13:34 退出，未触发 10 秒非暂停时长的失败超时。

原始日志保存在 `.local/native-audio-test/evidence/0.2.0-20261102-161234/`。

## 0.2.1 的验证点

保留已实测的状态检测；只替换音频适配器为游戏自带 WmfMedia + NativeAudioOut。
不创建 MediaSoundComponent，不调音量，不启动外部播放器，不新增 DLL。
0.1.1 曾成功打开 WmfMedia，但被 `SetNativeVolume=false` 提前中断，尚未实际验证播放；
这次完全移除该前置条件，并等到时钟推进后才恢复打开期间的 WMF 默认设置。

临时 WMF 设置属于共享内存默认值：打开、等待播放阶段可能影响并发打开的其他 WMF 媒体。
在推进、失败、停止、切换、打开期间暂停时恢复；不保存配置。Wwise 音乐总线并未接入，
不能宣称随游戏音乐音量滑块调节。原配乐不静音。当前只验证两首音乐与暂停/停止，不测语音叠加。

22 项离线检查验证玩法状态切换、清理和临时设置恢复，不验证实际 WMF 解码或扬声器输出。
## 2026-11-02：0.2.1 实机失败（交接时的最新证据）

用户再次反馈测试失败，并要求开新对话接手。已读取并保存这一轮日志：
`.local/native-audio-test/evidence/0.2.1-20261102-163320/`。

实际 `BOOT 0.2.1-native-gameplay-test` 在 16:33:20（香港时间）。16:33:56 清醒持剑，
16:34:03 进入微醺；触发与换曲均正常。两首歌都 `OPEN_REQUEST accepted=true`，
`MEDIA_READY backend=WmfMedia; audioTracks=1; selected=0`。
但是 `PLAY_REQUEST accepted=false`，持剑曲从 16:33:56 至 16:34:03 每秒重试都返回 false，
醉酒曲从 16:34:03 至 16:34:05 重试也都返回 false。没有进入 IsPlaying=true，
没有 CLOCK_ADVANCED。16:34:05 用户暂停，打开尝试被取消；16:34:13 游戏退出。
两次 `WMF_DEFAULT_RESTORED NativeAudioOut=false` 均有日志，发生在换曲及暂停取消时。

因此 WMF 原生输出方案也尚未成功。不能再宣称无声问题已经解决，
不能认为只换触发位置或不调音量就足够。下一步需调查 WMF 就绪却拒绝 Play 的具体原因，
并评估真正的游戏 Wwise 接法；调查方向不等同于已确定根因。
继续尊重用户边界：实际玩法测试、由用户操作游戏、先测接口不全面迁移、不要外部播放器。

参考：[Epic UWmfMediaSettings](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/WmfMediaFactory/UWmfMediaSettings)。

## 2026-11-02：只读定位与 0.3.0 进程内 DLL 测试

### WMF 排查发现的具体限制

对真正运行的 `platform/steam/PBZ.exe` 做了离线只读反汇编，没有启动游戏、
读写活进程或修改 EXE。局部分析工具和输出在 `.local/research/wmf_binary.py`、
`wmf-add-track.txt`、`wmf-rate-init.txt`。以下 RVA 仅记录该版本证据，测试代码不使用它们。
该 EXE 的 SHA256：`7b4fcd286a350780faf0824d73aa150b21cbf1bccde883e6a96386cbe09973b4`。

- WMF 音轨加入输出拓扑的函数位于 RVA `0x0876EED0`。音频分支先调用
  `waveOutGetNumDevs`，再检查一个引擎虚函数返回值（槽位 `0x410`），失败会提前退出。
  `NativeAudioOut` 默认值在之后的原生 renderer 分支才读取（RVA `0x0876F04F` 附近）。
  因此启用 `NativeAudioOut` 并不能绕过所有引擎声音检查。
- WMF 播放速率入口 RVA `0x08784C00` 会因会话缺失或速率不在支持范围内返回 false；
  支持范围来自媒体会话的速率服务，而不是仅根据文件已打开计算。
- 本机独立进程调用 `waveOutGetNumDevs` 得到 3。两个资源都只有音轨，无封面视频流：
  AAC-LC 48 kHz stereo 与 MP3 44.1 kHz stereo。

这些事实与已实测的 `WwiseOnly` 和 WMF 无法开始播放相符，为避开 Unreal 音频链路
提供依据。但 0.2.1 没有记录该引擎虚函数值、支持速率或内部 HRESULT，**尚不能证明
实机究竟命中了哪一个失败分支**。不能把静态分支发现写成已确认的动态根因。
本地 Wwise SDK 暴露事件播放和 AudioInput 组件，但没有现成的自定义音乐事件/声音库，
也没有可直接由 Lua 提供 PCM 的已验证回调；本轮不扩展到声音库制作或全面迁移。

### 新测试的明确变化

0.3.0 用一个约 151 KiB 的自编译 x64 DLL，通过 Lua `package.loadlib` 加载到游戏进程。
七个入口遵守 Lua C-function ABI，接收不透明状态指针、返回零个 Lua 值；不读取 Lua
内部结构、不依赖 UE4SS C++ ABI，也不含游戏地址或补丁。
工作线程调用 Windows WinMM `waveOut`；两首音乐在构建时转换为 48 kHz/16-bit/stereo PCM。
没有外部播放器 EXE 或自定义伴随服务，不调用音量 API，不改变 WMF/Wwise 设置。
此 DLL 未签名，不能保证不会被安全软件误报。

玩法 Lua 以命令编号匹配原生状态，旧状态不能误报成功；输出日志包含 PID、操作名、
错误码和设备样本计数。暂停/恢复使用设备接口，停止用 reset/unprepare/close。
加载过程中的过期请求在入队前取消，已入队后收到停止则重置设备。
心跳超过 3 秒中断会停声；失败只在新的玩法状态/玩家请求后重试。
DLL 固定在进程内直到退出，避免 Lua 清理时卸载仍运行的线程；不支持热重载。

仍不接 Wwise 音乐滑块，不静音原配乐，不测试语音。只有用户能确认实际游戏出声。
`gameplay.lua` 与正式 `core.lua`、`weapon.lua`、`settings.lua` 的 SHA256 与交接基线一致。
正式 `mods/JamieWin`、游戏安装目录和存档未修改。

### 验证与复现

- `python tests/test_native_audio_probe.py`：18 项 Lua mock 检查，覆盖状态优先级、
  去重、暂停、停止、超时、旧状态拒绝、DLL 加载失败和 F10。不是实机出声证据。
- `python tests/test_lua.py`：10 项正式 Lua 回归检查通过。
- `python tests/test_native_audio_device.py`：2 项实际 DLL / Windows 设备集成检查。
  仅在 Python/Lua 测试进程播放生成的静音缓冲，不操作 PBZ。
  验证设备计数超过四个循环、暂停后计数不变、恢复后推进、换曲、快速取消、坏文件失败、
  心跳超时停声，以及实际 Lua 适配器和状态文件的配合。静音输出不能证明正式音乐可听。
- 两个构建后的 WAV 已核对格式、非零样本与时长（约 201.024 / 167.369 秒）。
  不改变音量；MP3 时长与原容器时长的小差异包含解码器去除的编码填充。

构建工具为项目缓存中的 Zig 0.13.0 和已有 FFmpeg，均不进入 ZIP。
`tools/build-native-audio-test.ps1` 只产生 `.local/native-audio-build/`；
`tools/package-native-audio-test.ps1` 构建并打包到 `.local/releases/`，不安装到游戏。
测试默认不启动 PBZ。新包由用户更新同一个 `JamieWinNativeAudioTest` 后手动测试。

接口依据：
[Lua package.loadlib](https://www.lua.org/manual/5.4/manual.html#pdf-package.loadlib)、
[waveOutGetPosition](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-waveoutgetposition)、
[WAVEHDR 循环标记](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/ns-mmeapi-wavehdr)。

### 0.3.0 交付记录（17:02 构建，香港时间）

- ZIP：`.local/releases/JamieWin-0.3.0-NativeGameplayTest-ModOnly-20261102-170238.zip`，
  68,174,551 字节（约 65.0 MiB），13 个文件。
- SHA256：`0390f31cc55b451d862d1075a4bac059ff2dd0d33583e33a6c1de7dafb66af8c`。
- DLL SHA256：`db027496f926bc06304fdbe71b7290891d06efe916d6eede6a338d3141c94e0e`。
- 构建后重新运行 18 + 10 + 2 项检查，全部通过。设备证据目录：
  `.local/native-audio-test/device-check-c3a48bb2aac043e6aea80f0efe88f088/`；
  适配器集成证据目录：`.local/native-audio-test/adapter-device-check-9138695befac43edb30628e65357efb3/`。
- ZIP 内 DLL、两首 WAV、7 个 Lua 与已验证的本地构建/源码字节一致，CRC 和 Lua 语法通过。
  DLL 仅导入 Windows 库，没有进程启动或音量设置接口。完整清单在
  `.local/native-audio-test/package-verification-0.3.0.json`。
- **未安装、未启动游戏、未实机试播**。等待用户用管理器更新独立测试 Mod 并操作游戏。

## 2026-11-02：0.3.0 用户确认通过，0.4.0 补齐完整功能

用户明确反馈「这次测试通过了」，并要求实现音量和剩余功能。已保存本轮实机日志到
`.local/native-audio-test/evidence/0.3.0-20261102-170726/`。游戏日志的 BOOT 在 17:07:26，
DLL 于 17:08:58 在 PBZ PID 35560 内启动；持剑曲和醉酒曲的设备计数均推进，暂停后
计数保持不变。**本轮出声结论来自用户实听确认，设备计数仅作为辅助证据。**
已通过的 0.3.0 源码和工具保存在 `.local/archive/native-probe-0.3.0-confirmed/`。

### 0.4.0 的实现

- 原生层拆分为 `Native/audio.c`（设备和命令）与 `Native/mixer.c`（PCM 混音）。
  四份资源统一为 48 kHz stereo PCM16，总 PCM 数据约 68.33 MiB。
  通过四个 20 ms 缓冲持续输出，两种语音为独立的一次性通道，音乐在软件中循环。
  音量作用于样本，不调用 `waveOutSetVolume` 或更改 Windows 会话/设备音量。
- 音乐增益为 `OverallVolume * MusicVolume * .45`，四酒和处决分别为
  `OverallVolume * DialogueVolume * .9`、`OverallVolume * DialogueVolume`。
  语音期间音乐平衡从 .45 降至 .20，并用短增益渐变恢复，求和后饱和限制防止整数回绕。
  不引入用户音量配置文件。
- `game_audio.lua` 用 `PBZSoundFXSubsystem:SetAudioVolume(2, ...)` 接管音乐 RTPC。
  先准备四份音频和设备，再静音原乐，后续游戏帧回读确认后才允许输出音乐；停止时
  检查已排队缓冲的音乐标记，确认停声后才恢复当前 `SharedSettings.MusicVolume`。
  原有设置始终只读，不调用 SaveSettings。原乐恢复未完成时继续轮询，包括 F10。
- `executions.lua` 沿用四个醉剑处决类和已验证的事件适配方法，过滤本地角色、有效目标
  及目标生命值，在激活时请求语音；同一能力的继承回调去重，结束后重新允许下一次激活。
  Native 函数使用 post hook，Blueprint 函数使用 UE4SS 的 post callback；回调不返回值。
  新进入大醉由共享 Core 的计数变化触发，持续大醉不会重复，换玩家不补播历史计数。
- 暂停保持当前音乐及语音位置；暂停期间的新语音等待继续。死亡、标题、玩家丢失和
  F10 清空全部输出。没有外部播放器、伴随服务、运行时转码或游戏地址补丁。

四个零返回值的 Lua C ABI 入口为 Init、Apply、Stop、Heartbeat。Lua 写完并关闭
`native-command.txt` 后，Apply 同步读取完整 JWN4 快照，工作线程只读取锁保护的结构。
协议携带会话、单调序号、玩家代次、活动/暂停/音乐许可、三个增益与两个语音计数，
拒绝错误会话、倒退序号、截断数据、越界值和非有限增益。状态文件原子替换，包含
相同会话/序号、设备计数、真实停止确认和独立的语音状态。

停止命令不续租，原生心跳超时 3 秒停声；Lua 不能取得停声确认时，等待至少 5 秒
（超出心跳和最多 80 ms 排队时长）再释放原乐。严重卡顿可能触发这一保护；Lua
恢复后才能执行游戏 RTPC 恢复。失败只在新的曲目/玩家请求后重试，不每帧反复打开设备。
DLL 固定到游戏进程退出，不支持热重载。

### 验证与交付

- 25 项 Lua 检查通过：音量乘积、静音与停声确认顺序、恢复最新偏好、设置/写入失败恢复、
  双语音计数、继承回调去重、暂停待播、F10 及超时等。
- 原有 10 项共享/旧版 Lua 回归通过。正式 core/weapon/settings 与先前哈希一致。
- 6 项实际 C 混音样本检查通过：增益和零音量、压低/恢复、双语音混合与结束、循环与
  同曲续播、溢出饱和、停止清空。测试可执行文件只留在项目缓存，不进入 ZIP。
- 4 项实际 Lua/DLL/Windows 音频设备检查通过，只播放生成的静音数据。覆盖准备阶段
  不入队、滑块更新不重播、暂停与待播语音、双语音完成、错误数据拒绝、快速替换、
  坏音频失败、心跳停声，以及实际 Lua 协调器与设备的配合。
- 设备检查曾发现短暂状态文件读取失败会撤回许可导致重播；已改为在同一玩家代次内
  保留设备准备确认，直到明确失效或超时。新增回归检查覆盖临时文件竞争和待确认命令。
- 打包重编译只改变了 DLL 的 PE 时间戳，但仍对包内的最终 DLL 重跑了全部 4 项设备检查。
  最终证据目录：
  `.local/native-audio-test/full-adapter-device-check-06ff7ca64afc46a99f74f73316b2694b/`、
  `bad-pcm-device-check-fcaee6d62f2444958a6ef123aa7af9a5/`、
  `packet-device-check-3ee700e9ff3844dc9b26df3f6ccd8d33/`、
  `full-device-check-98934c931f3b47b2a024672da180d28b/`（后三者位于同一父目录）。

17:45:35（香港时间）生成：

- ZIP：`.local/releases/JamieWin-0.4.0-NativeFullTest-ModOnly-20261102-174535.zip`。
- 大小：68,800,932 字节，约 65.6 MiB；17 个文件。
- ZIP SHA256：`3a5f817911aa2ef8e149c750e694810276e2b675c2d45869f4c331eb45c37802`。
- DLL SHA256：`842b04d58e59deab897fc17298b49a0f6af5bcbc368f2adb52ba83b054a78702`，158,208 字节。
- 完整清单与检查结果：`.local/native-audio-test/package-verification-0.4.0.json`。
  ZIP CRC、精确文件清单、9 份 Lua 语法与字节匹配、4 份 WAV 格式和非零样本、
  DLL 架构/导出/导入及最终设备测试 DLL 哈希全部通过。不含 EXE、加载器或构建工具。

安装目录仍为 `JamieWinNativeAudioTest`，由用户退出游戏后通过管理器更新。
**0.4.0 新功能尚未在 PBZ 内验收**。本轮没有启动/控制游戏或写入游戏安装目录；
安装包中的 `runtime` 仅有占位文件。当前使用说明已更新到根 README，旧外部播放器
说明保留在 `docs/legacy-external-player.md`，原 `mods/JamieWin` 实现仍保留供比对。

接口依据：[waveOutWrite](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-waveoutwrite)、
[waveOutReset](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-waveoutreset)、
[UE4SS RegisterHook](https://docs.ue4ss.com/dev/lua-api/global-functions/registerhook.html)。

### 0.4.0 元数据与包名修正（同日 17:56）

用户指出版本应记录在格式化文件中。新增 `probes/JamieWinNativeAudioTest/mod.json`，
名称固定为 `JamieWin`，版本单独为 `0.4.0`，安装 ID 保持 `JamieWinNativeAudioTest`。
打包脚本从该文件读取版本，拒绝不一致的命令行版本，并校验 Lua 与 DLL 的内部版本。
元数据随整个 Mod 目录部署，供人工和项目工具读取。

核对本机 UE MM 文件版本为 1.4.1，对应提交 `40b56f5290914750c14deb384ceac5bb0a3c398a`。
该版本的本地导入只通过 `ModNaming.FromSource` 从下载名提取名称和版本，不读取
包内的 `mod.json`。旧包把版本置于中间、后面再加标签和时间戳，无法被其尾部版本规则识别。
因此新 ZIP 使用 `JamieWin-0.4.0.zip`：管理器的名称字段为 JamieWin，Version 字段为 0.4.0。
时间戳移到包外的归档目录；没有更改管理器程序或已安装的记录。
依据：[命名解析](https://github.com/KintaroModding/uemodmanager/blob/40b56f5290914750c14deb384ceac5bb0a3c398a/src/UEManager.Core/Mods/ModNaming.cs)、
[导入流程](https://github.com/KintaroModding/uemodmanager/blob/40b56f5290914750c14deb384ceac5bb0a3c398a/src/UEManager.Core/Mods/ModManager.cs)。

新包：`.local/releases/20261102-175629/JamieWin-0.4.0.zip`，共 18 个文件。
SHA256：`89280475a5856a51b938983f053b34504c9609ba804e0fbc5c4854bcea880cca`。
旧发布包保留。新包仅增加元数据、更新说明和命名；9 份 Lua、4 份音频与已验证包字节一致，
DLL 仅 PE 文件头及调试目录时间戳变化，归零时间戳后逐字节一致。
已验证 ZIP CRC、文件集合、元数据、管理器尾部命名规则和版本覆盖拒绝。
报告：`.local/native-audio-test/package-verification-0.4.0-metadata.json`。

## 2026-11-02：0.5.0 菜单滤波与连续播放

用户确认《鸳鸯戏》24 秒滤波试听，并要求接入游戏：进入菜单变闷、退出恢复清晰，
歌曲持续向前播放。基于已经完成的 0.4.0 分块混音链路实现，保留音量滑块、原乐
接管与恢复、四酒和处决语音。正式旧外部播放器实现未迁移。

- `Native/menu_filter.c` 使用两个 1200 Hz、Q=0.70710678 的双二阶低通，滤波分支
  额外乘以 .9。清晰与滤波信号按 0.4 秒余弦曲线混合，参数与已确认的试听一致。
  滤波只作用于音乐；左右声道状态独立，清晰状态也保持滤波器预热。
- 菜单切换只改变混合比例，不再调用 waveOutPause/waveOutRestart，也不关闭设备、
  清空排队音乐或重置歌曲游标。过渡中反向操作从当前比例继续，重复相同请求不重开渐变。
- 语音在菜单内保持位置，新语音计数等待退出后处理；音乐持续前进。停止/死亡/标题/
  F10 仍清空播放和滤波状态。菜单中调游戏音量沿用原有样本增益，不重播。
- 游戏暂停信号沿用已实测的 IsGamePaused。对于不暂停世界的菜单，额外读取本地玩家
  的 PBZSystemScreenWidget/PBZGameSystemWidget 根控件，要求同时激活且可见。
  控件发现每秒最多一次、已有控件状态每次玩法采样检查；新建的不暂停菜单最多增加
  约一秒发现时间。常规暂停菜单沿用 200 ms 采样，再加最多 80 ms 音频队列。
  根类与接口见本机 ProjectPBZ.hpp/CommonUI.hpp；这些非暂停控件的实机覆盖仍待用户确认。
  FindAllOf 的继承实例查找依据：[UE4SS 文档](https://docs.ue4ss.com/lua-api/global-functions/findallof.html)。
- 内部快照升级为 JWN5，将原暂停字段改为菜单效果字段；拒绝旧 JWN4 快照，避免旧脚本
  与新 DLL 混用时误解语义。状态增加 menu/menu_mix，日志增加 MENU ENTER/EXIT 和播放计数。

本轮本地验证已完成：28 项协调器/音量/事件检查、4 项菜单检测检查、10 项原有 Lua 回归、
9 项 C 混音检查、1 项真实音乐离线渲染对比、4 项 Windows 设备检查。设备测试仅在独立
测试进程播放生成的静音数据，没有启动或操作 PBZ。最后一组设备检查启动后，用户明确
表示由自己负责测试；随后只收取已运行检查的结果和核对安装包，没有再启动测试。

离线渲染通过正式 C 混音器生成 24 秒音频，以相同 PCM 输入和试听参数的 FFmpeg 输出
为独立参考。最大误差小于 1 个 PCM16 整数量化单位，输出无削波，音乐累计前进
1,152,000 帧。报告及试听文件在
`.local/native-audio-test/menu-preview-check-d413b37413ef4930aec3fd7caf88f35f/`。
设备检查确认进入/退出菜单、快速开关与音量变化时，设备和音乐计数持续前进，未重新
准备设备；语音等待和恢复、旧协议拒绝、停止确认、坏文件与心跳保护均通过。
设备证据目录位于 `.local/native-audio-test/`：
`full-adapter-device-check-3d19dae4abba4095b740bd4a753106af/`、
`bad-pcm-device-check-066c777a47434a83917399a8909868fe/`、
`packet-device-check-0d600ee5c44245d0967bb7e4514954be/`、
`full-device-check-a78aa271a56e4cdaa904b874ac739f5e/`。

18:16:41（香港时间）生成 `.local/releases/20261102-181641/JamieWin-0.5.0.zip`，
68,803,117 字节、18 个文件；元数据名称 JamieWin、版本 0.5.0，安装 ID 不变。
SHA256：`cf6668e500751558427dd22fd5bfcabadd77d77542b581d8df143b4ac1391b32`。
构建结果记录于 `.local/native-audio-test/release-0.5.0.json`。没有写入游戏安装目录；
由用户完全退出游戏后通过管理器更新并进行游戏内试听验收。

## 2026-11-02：1.0.0 正式版

用户确认最新 0.5.0 候选包测试通过，并要求升级为 1.0.0 后提交。
`mod.json` 版本改为 `1.0.0`、渠道改为 `stable`，Lua 与 DLL 内部版本同步为
`1.0.0-stable`。安装 ID 继续使用 `JamieWinNativeAudioTest`，播放逻辑、混音参数和
音频资源沿用已验收版本；README 与包内说明更新为正式版状态。

18:28:52（香港时间）生成 `.local/releases/20261102-182852/JamieWin-1.0.0.zip`，
68,803,126 字节、18 个文件。
SHA256：`bb671e984be6c6949d76eefe6b1171c7a7e1943dba7e2986dea0da1226a871ac`。
构建结果记录于 `.local/native-audio-test/release-1.0.0.json`。

本轮构建及发布包检查通过：ZIP CRC、文件集合、SHA256、元数据、Lua/DLL 内部版本
与源码一致。对比 0.5.0 包，4 份音频与 8 份业务 Lua 字节一致，仅版本配置、DLL、
元数据和说明文件变化。游戏内验收采用用户本次确认的结果。

## 2026-11-02：1.0.1 原始音频与单曲音量

直接打包 `mr_top_player.m4a` 和 `mandarin_duck_play.mp3`，不重新编码两首音乐。
新增 `Native/media_decode.c`，通过 Windows Media Foundation 在工作线程内解码为
48 kHz、双声道 PCM16，再交给原有混音器；不生成运行时 WAV，不需要外部播放器。
参考：[Microsoft Source Reader 解码说明](https://learn.microsoft.com/en-us/windows/win32/medfound/tutorial--decoding-audio)。
解码验证输出格式、64 MiB 上限和错误清理，停止全部音频时释放 PCM。

只将《Mr.Top.Player》的混音增益乘以 1.2（约 +1.58 dB），正常/语音压低时的默认
增益分别为 0.54/0.24；《鸳鸯戏》和两段语音保留原有音量。游戏音量滑块、零音量、
菜单渐变、循环位置和语音压低仍由原混音器处理。

本轮验证通过：46 项 Lua 回归、10 项 C 混音检查、菜单滤波离线对照、原始音频解码
对照与 5 项静音设备检查。M4A 解码与 FFmpeg 参考在测试窗口逐样本一致；MP3 重采样
后的相关度为 0.99946，解码器首尾填充导致总时长约多 63.5 ms。两首本机首次解码
分别耗时 984 ms、750 ms。解码对照还覆盖中文路径、损坏/缺失文件与 PCM 容量上限。
证据位于 `.local/native-audio-test/decode-check-dd5265aaca59439d9f11689a14bec89a/`；
菜单与设备证据使用同目录下本轮 `menu-preview-check-*`、`*-device-check-*` 目录。
未启动或操作游戏，本次改动尚未做游戏内试听验收。

20:42:09（香港时间）生成 `.local/releases/20261102-204209/JamieWin-1.0.1.zip`，
10,636,707 字节（10.64 MB / 10.14 MiB），相比 1.0.0 缩小 84.54%。
SHA256：`bde0ecffa56b9079de05111d334014d016427b02d823dd88e733c794cd484e15`。
构建记录为 `.local/native-audio-test/release-1.0.1-audio.json`。
已核对 ZIP CRC、18 个文件、SHA256、版本一致性、两首音乐与源文件字节一致，
两段语音与 1.0.0 包字节一致，包内不含旧音乐 WAV。
包按当前工作区 Lua 源码生成，也包含同步进行的处决动画触发修复；本轮没有覆盖该修改。

## 2026-11-02：1.0.2 音量与音效叠加

按用户要求，《Mr.Top.Player》在 1.0.1 基础上再提高 20%：单曲系数从 1.2 改为
1.44，默认音乐增益从 0.54 改为 0.648。《鸳鸯戏》仍为 0.45。
移除四酒和 Jamie wins 播放时的音乐自动压低，两段音效单独或同时触发时直接混音，
两首歌曲保持增益和播放位置；语音音量、游戏滑块、菜单滤波与语音菜单暂停规则沿用。
音乐和语音源文件均未修改，仍使用原始 M4A/MP3 小体积打包。

验证通过：46 项 Lua 检查、10 组 C 混音回归、菜单滤波离线参考以及 5 项静音设备
检查。新增混音断言覆盖两首歌与两种音效单独/同时叠加，在触发瞬间、播放期间和结束
后检查实际 PCM、增益、音乐帧计数与循环位置。设备检查在正常换曲淡入后确认语音
期间增益保持 0.648（滑块缩小场景为 0.144）或 0.45。菜单滤波参考最大误差仍小于
1 个 PCM16 单位。新版未进行游戏内试听，所有设备检查只播放生成的静音。
菜单证据：`.local/native-audio-test/menu-preview-check-aec7c97a599d4f7ab9205d7c1c7be87a/`。
完整设备证据：`.local/native-audio-test/full-device-check-76eed3418ede4d77893f69fa4d3a3e17/`。

21:12:42（香港时间）生成 `.local/releases/20261102-211242/JamieWin-1.0.2.zip`，
10,636,713 字节（10.64 MB），18 个文件。
SHA256：`5ed2d68643fe1ae392b5ca8d63b2637315efb8295a04b182f9ae235cd083e26a`。
ZIP CRC、版本、源码与包内 Lua 对应、全部音频与 1.0.1 字节一致的检查均通过；
构建与校验记录为 `.local/native-audio-test/release-1.0.2-audio.json` 和
`.local/native-audio-test/release-verify-1.0.2-audio.json`。

## 2026-11-03：1.1.0 发布验证

将当前音频与处决更新统一为 `1.1.0`，Lua 和 DLL 内部版本为 `1.1.0-stable`。
包含原始 M4A/MP3 解码、Mr.Top.Player 音量提升、语音叠加时保持音乐音量与进度，
以及成对处决动画开始后延迟 2000 ms 播放 Jamie wins。安装 ID 继续沿用
`JamieWinNativeAudioTest`。

本地验证通过：37 项音频适配、4 项菜单检测、10 项共享 Lua、10 组 C 混音、
两首原始音乐的离线解码对照、菜单滤波参考和 5 项静音设备检查。
安装包包含 18 个文件；ZIP CRC、SHA256、版本一致性、包内 Lua 语法及原始音乐
字节一致性检查全部通过。此轮没有进行游戏内试听。

本地构建：`.local/releases/20261103-002821/JamieWin-1.1.0.zip`，10,637,150 字节。
SHA256：`3fdff9e6baf841a777c5a9e113cb85abb6b536b15602b68775ba405706b7096e`。
GitHub Release 由对应标签触发云端重新构建，公开附件以 Release 页面上的校验值为准。

# 2026-11-02：重击误播 Jamie wins 的修复

用户要求在实际开始处决敌人时播报，而不是出现可处决提示或处决完成时。
旧版在 `K2_ActivateAbility` 回调中，仅凭白名单能力和存活目标就增加语音计数。
白名单还包含两个 `GA_SimpleExecution_ChiZheCanJian*` 类，没有验证成对处决动画。
本机旧版日志中的多次 `SimpleExecution` 激活均增加了 `wins`；这些日志没有记录动画
开始证据，不能证明发生了真正的处决。

## 触发条件

- 白名单只保留醉剑的 `GA_Hun_BEx_ChiZheCanJian_M_01_C` 和 `_M_02_C` 执行者能力。
- 监听继承自 `GA_ExecutionAbilityBase_C` 的 `Play Execution`，不再监听能力激活。
- 回调后要求 `ExecutionTimeline` 有效，且 `IsPlayingTimeline` 返回 `true`。
- 能力主人、`Execution Info.Executor` 都必须是当前本地玩家，`IsTarget` 必须为
  `false`，目标必须是另一个仍存活的角色；暂停、菜单、死亡和 F10 停用仍然拦截。
- 同一次能力期间只增加一次计数；`K2_OnEndAbility` 只清理去重状态，不请求语音。

这些接口来自本机 Steam build `26266538` 的 `CXXHeaderDump/GA_ExecutionAbilityBase.hpp`、
`SGameExecution.hpp`、`LegoAbility.hpp` 和 `UE4SS_ObjectDump.txt`。对象转储包含
`Play Execution` 内调用 `PlayTimeline` 的参数，以及 `IsPlayingTimeline` 的布尔返回值。
Blueprint 回调使用执行后的 hook，原生结束函数使用 post hook，回调不返回游戏值；
参数位置依据 [UE4SS RegisterHook 文档](https://docs.ue4ss.com/lua-api/global-functions/registerhook.html)。

日志中的 `EXECUTION_BEGIN` 现在包含 `source=Play Execution; timeline playing`；
未开始播放或执行者信息不匹配时记录 `EXECUTION_START_IGNORED`。

## 验证

新增回归用例先在旧实现上复现了仅激活能力、残留存活目标也播报的问题。
修复后 `test_native_audio_probe.py` 的 32 项、`test_lua.py` 的 10 项及
`test_native_menu_detection.py` 的 4 项全部通过，其中处决适配覆盖 8 项场景及子用例：
普通重击、SimpleExecution、可处决信息、未播放/缺失动画、双处决类型、弱引用、
继承去重、结束后再次处决、错误执行者、死亡/菜单/停用、hook 重试与查询异常。

这里只完成离线逻辑验证，游戏内开场时机仍待复测。退出游戏后通过 UEMM 更新，
再检查连续重击和仅靠近可处决敌人不播报；实际发动两种醉剑处决应在开场各播一次，
处决结束不补播。未修改游戏安装目录、战斗状态或存档。

## 安装包

本次修复与工作区中原始 M4A/MP3 播放、Mr.Top.Player 音量调整一起打入 1.0.1。
包位于 `.local/releases/20261102-204245/JamieWin-1.0.1.zip`，10,636,706 字节，18 个文件。
SHA256：`e16a9a53a306347084bc2a62dda401d6bb98baacd2552e30fb0bb4e332bbd2e4`。
构建前后源码哈希一致；ZIP CRC、文件集合、9 份 Lua 的字节一致性与语法、版本和校验值均通过。
构建信息位于 `.local/native-audio-test/execution-start-fix-package.json`。

## 1.0.3：处决语音延迟 1 秒

按用户后续反馈，确认处决开始后先排队，满 1000 ms 才增加语音计数。
`settings.lua` 的 `ExecutionVoiceDelayMs` 固定为 1000；使用
[ExecuteWithDelay](https://docs.ue4ss.com/lua-api/global-functions/executewithdelay.html)
计时后回到游戏线程检查玩家状态并请求播放，不阻塞游戏线程，也不使用整秒时间戳计时。

去重状态与待播事件分别保存，处决提前结束或目标在等待期间死亡不会丢掉已经确认的
处决开始事件。玩家死亡、切图、更换玩家或 F10 停用会取消待播语音；菜单继续沿用
现有语音暂停/恢复逻辑。普通重击与可处决提示仍然不排队，结束回调不会新建播报。

延迟回归检查覆盖第 999 ms 不播、第 1000 ms 只播一次、重复回调、短处决、目标死亡、
玩家死亡/切换/短暂失活、停用、菜单及计时失败。整体 37 项音频适配检查、10 项共享 Lua
检查和 4 项菜单检查通过。游戏内实际听感仍待用户复测。

1.0.3 包：`.local/releases/20261102-212907/JamieWin-1.0.3.zip`，10,637,155 字节。
SHA256：`7cc5c34b5d7d7837439bc9d52adc7a69a7383f191d4293f173444d3051db6917`。
构建前后源码一致；包内 1000 ms 配置、9 份 Lua、DLL 版本、18 项文件集合、CRC 与校验值均通过。
构建记录：`.local/native-audio-test/release-1.0.3-execution-delay.json`。

## 1.0.4：在实听时机上再后移 1 秒

用户反馈 1.0.3 听起来没有延迟。核对已安装文件和 UE4SS 日志，确认运行的是
1.0.3，配置为 1000 ms；旧外部播放器版本没有同时运行。21:42:04 至 21:43:04 的
5 次处决从 `EXECUTION_BEGIN` 到 `EXECUTION_VOICE` 相隔约 1.006～1.020 秒，
原生 `CUE win` 也在后者之后。这证明延迟请求已生效，不能据此替代用户对声画时机的判断。

用户随后明确选择“比现在再晚 1 秒（总延迟 2 秒）”。将 `ExecutionVoiceDelayMs`
从 1000 改为 2000；沿用已经确认的处决开始事件与取消规则。37 项音频适配检查通过，
其中两个处决类型在第 1999 ms 不播、第 2000 ms 各播一次。新听感待用户复测。

安装包：`.local/releases/20261102-215330/JamieWin-1.0.4.zip`，10,637,148 字节。
SHA256：`6f65c055015f75f819d4ed1f96f088ae3217d71e90cc14c2ecb533cf44e55992`。
源码一致性、包内 2000 ms 配置、Lua 语法、版本、文件集合、CRC 和校验值均通过；
4 份音频与 1.0.3 字节一致。构建记录：`.local/native-audio-test/release-1.0.4-execution-delay.json`。

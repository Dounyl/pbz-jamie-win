JamieWin 1.2.0 事件驱动版 · 影之刃零醉剑音频 Mod

通过 UEMM（UE MM）安装，装好后正常进游戏就能用。
四酒和 Jamie wins 音效直接叠加，背景音乐保持音量和进度。
两首音乐使用原始 M4A / MP3，小体积打包。
游戏状态改为钩子触发读取，取消定时游戏状态轮询；音频心跳和播放确认独立维护。
实际回调覆盖及卡顿改善待游戏内复测。

安装
UEMM 下载地址：https://github.com/KintaroModding/uemodmanager/releases

1. 先退出游戏。
2. 下载 UEMM，解压后运行 UEModManager.exe；没自动找到游戏，就在设置里选游戏目录。
3. 在 UEMM 的 UE4SS 页面安装适配游戏的 UE4SS，已有兼容版本就跳过。
4. 把 JamieWin-1.2.0.zip 拖进 UEMM，确认名称 JamieWin、版本 1.2.0，安装并启用。
5. 从 Steam 正常启动游戏。

ZIP 直接导入，不用手动解压。
安装预览中的文件应放在 platform/steam/ue4ss/Mods/JamieWinNativeAudioTest/。
UEMM 使用说明：https://github.com/KintaroModding/uemodmanager/blob/main/openmods.md

怎么播放
- 清醒且实际手持醉剑：循环《Mr.Top.Player》。
- 微醺或大醉：循环《鸳鸯戏》；两种醉态互换不重播。
- 每次新进入大醉：四酒日语语音一次。
- 醉剑成对处决动画实际开始且目标仍存活：延迟 2 秒播放一次 Jamie wins。
  普通重击、可处决提示和处决完成不触发；本次触发修复待游戏内复测。
- 语音、音效直接叠加播放，Mod 背景音乐保持音量和进度。
- 打开暂停、设置或系统菜单：音乐继续，声音逐渐变闷；语音暂停。
- 退出菜单：音乐恢复清晰，不从头播放；语音继续。
- 清醒时收剑或换武器：停止 Mod 音乐，恢复原配乐。
- 死亡或回到标题界面：停止 Mod 音乐和语音，恢复原配乐。
- F10：本次游戏停用 Mod，恢复原配乐；重启游戏后重新启用。

读档时如果已经大醉，不会补播四酒语音。Mod 只改声音，不改角色数值、战斗和存档。

调音量
直接用游戏里的设置：音乐音量控制背景音乐，对话/语音音量控制语音，总音量控制全部。
播放语音或音效时，Mod 背景音乐不会被压低、暂停或重播。
调音量不会让歌曲重播，收剑后原配乐按你最新设置的音量恢复。

更新、停用和卸载
先退出游戏，再到 UEMM 里选中 JamieWin 操作。更新时用新的 ZIP 更新现有条目。
同时只启用一个 JamieWin 版本。

遇到问题
间歇性卡顿可在同一场景对比按 F10 前后各 30 秒的流畅度。
更新后检查日志中的 BOOT 1.2.0-stable 和 EVENT_MODE，确认实际加载了事件版。
复测拔收剑、切武器、微醺/大醉/自然醒酒、菜单、音量、死亡/复活、读档和处决。
出现漏切歌、菜单效果不退出或 EVENT_ERROR / FAIL 时，请附操作步骤和日志。
反馈时说一下做了什么、听到了什么，并附上这些日志：
- Mod 文件夹下 runtime/ 里的 native-audio-test.log、native-output.log 和 native-status.txt。
- platform/steam/ue4ss/UE4SS.log。

已验证环境
Windows x64、PBZ Steam build 26266538、UE4SS v3.0.1-1195-g1ceefac8。
其他版本还没测过。源码结构和验证方法见源码中的 docs/development.md。

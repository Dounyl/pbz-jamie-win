JamieWin 0.8.0 候选版 · 影之刃零醉剑音频 Mod

适配：Windows 64 位，Steam build 26266538。

验证状态
本地播放器与便携配置测试已通过。
从 Steam 启动后自动拉起播放器，以及管理器导入、停用、更新、卸载和旧安装迁移，尚未完成本 Mod 的实机验证。

管理器安装方案（待实测）
推荐 Phantom Blade Mod Manager（UE MM），2026-11-02 已核对版本为 1.4.1，支持简体中文。
下载：https://github.com/KintaroModding/uemodmanager/releases
1. 退出游戏，打开管理器并选择 PBZ 游戏目录。
2. 首次使用时，通过管理器安装适配 PBZ 的 UE4SS；已有兼容加载器时保留原有安装。
3. 拖入 JamieWin 的 ModOnly ZIP，检查文件均部署到 platform/steam/ue4ss/Mods/JamieWin 后安装并启用。
4. 后续通过管理器停用、更新、卸载。不要把 Full 包作为 JamieWin 的常规更新包导入。
已有手动安装时，先备份 JamieWin 文件夹和音量设置，退出旧播放器，将旧 JamieWin 文件夹移出游戏目录，再通过管理器安装。

手动解压安装
1. 完全退出游戏。在 Steam 中打开“管理 → 浏览本地文件”，进入 PBZ 游戏根目录。
2. 将 ZIP 解压到这个 PBZ 目录，或把压缩包里的 platform 文件夹复制进去并合并文件夹。
3. 候选版预期正常从 Steam 启动游戏即可，无需手动运行安装或播放脚本；自动启动流程仍待实机验收。

正确的目录结构（不要额外套一层 JamieWin 文件夹）：
PBZ
└─ platform
   └─ steam
      ├─ PBZ.exe（游戏原文件）
      ├─ dwmapi.dll
      └─ ue4ss
         └─ Mods
            └─ JamieWin
               ├─ Scripts
               ├─ Player
               ├─ Audio
               ├─ runtime
               ├─ audio.json
               └─ enabled.txt

选择哪个包
- Full 完整包：没有安装过 UE4SS 的玩家使用，包含适配加载器。
- ModOnly 仅 Mod 包：已安装适配 PBZ 的 UE4SS v3.0.1-1195-g1ceefac8 时使用，避免覆盖已有加载器设置和其他 Mod。
两个包都解压到 PBZ 游戏根目录。

使用
候选版设计为游戏启动时自动启动音频、退出游戏后播放器自动退出，验证状态见上方。
清醒持醉剑播放 Mr.Top.Player，微醺或大醉切换鸳鸯戏，清醒后持剑则切回。
新进入大醉播放四酒音效；发动醉剑处决立即播放 Jamie wins。
Mod 歌曲播放时原游戏配乐静音；清醒收刀、换武器或角色死亡后恢复原配乐。

音量
编辑 platform\steam\ue4ss\Mods\JamieWin\audio.json：
MusicVolume=0.45，DrinkVolume=0.9，WinVolume=1.0，DuckVolume=0.2。
数值范围为 0 到 1，改动后重新启动游戏。更新前可备份自己的音量设置。

卸载
通过管理器安装的版本：退出游戏后在管理器内卸载。
手动安装的版本：退出游戏及播放器，删除 platform\steam\ue4ss\Mods\JamieWin。
若使用其他 UE4SS Mod，请保留 dwmapi.dll 和其余 ue4ss 文件。

日志
platform\steam\ue4ss\Mods\JamieWin\runtime\game.log
platform\steam\ue4ss\Mods\JamieWin\runtime\audio.log

加载器来源：https://github.com/KintaroModding/ue4ss/releases/tag/v3.0.1-1195-g1ceefac8
UE4SS 原项目：https://github.com/UE4SS-RE/RE-UE4SS
完整包保留上游 ue4ss/LICENSE。

# JamieWin · 影之刃零醉剑音频 Mod

给醉剑配上杰米的音乐与语音：清醒持剑时听《Mr.Top.Player》，喝到微醺或大醉时切换《鸳鸯戏》，再用一声「Jamie wins」为处决助兴。

## 简介

| 游戏中的状态或动作 | 你会听到什么 |
| --- | --- |
| 清醒时手持醉剑 | 循环播放《Mr.Top.Player》；只放在背包里不会触发 |
| 进入微醺或大醉 | 切换为循环播放《鸳鸯戏》 |
| 微醺与大醉互相切换 | 《鸳鸯戏》继续播放，不从头开始 |
| 每次新进入大醉 | 播放一次杰米四酒日语音效 |
| 发动醉剑处决 | 动作开始时播放一次「Jamie wins」 |
| 恢复清醒 | 仍手持醉剑时切回《Mr.Top.Player》，否则恢复游戏原配乐 |
| 清醒时收起或换下醉剑、角色死亡、回到无玩家的界面 | 停止 Mod 音乐，恢复游戏原配乐 |

Mod 音乐播放时会暂时静音游戏原配乐，结束后自动恢复。只改变听到的音乐和语音，不修改游戏数值、战斗逻辑或存档。

## 版本与验证状态

适用于 Windows 64 位、《影之刃零》Steam build `26266538`，依赖适配 PBZ 的 **UE4SS `v3.0.1-1195-g1ceefac8`**。其他游戏版本和商店版本尚未验证。

**0.8 当前是候选版本。** 本地播放器与便携配置测试已通过；从 Steam 启动后自动拉起播放器、通过管理器导入／停用／卸载的完整流程尚未完成实机验证。以下是候选包的安装方案，不代表这些流程已经验收通过。

旧版 `JamieWin-0.7.0-*.zip` 使用安装与启动脚本，不能按下面的 0.8 步骤直接使用。旧安装器已停止维护，当前只构建独立模组包。

## 使用管理器安装

推荐使用 [Phantom Blade Mod Manager（UE MM）](https://www.nexusmods.com/phantombladezero/mods/2)。截至 2026-11-02，已核对的版本为 **1.4.1**，支持简体中文与 UE4SS 模组管理。管理器会显示文件去向，记录部署文件，并负责启用、停用、更新与卸载；PBZ 的正确路径是 `platform/steam`。[管理器说明](https://github.com/KintaroModding/uemodmanager)

1. 完全退出游戏。从 [作者发布页](https://github.com/KintaroModding/uemodmanager/releases) 下载管理器，解压后运行 `UEModManager.exe`，按提示选择 PBZ 游戏目录。管理器需要 [.NET 8 Desktop Runtime（x64）](https://dotnet.microsoft.com/download/dotnet/8.0)。
2. 首次使用时，通过管理器的 UE4SS 页面安装[适配 PBZ 的加载器](https://www.nexusmods.com/phantombladezero/mods/13)。已有兼容加载器时保留原有安装。
3. 将 **`JamieWin-0.8.0-ModOnly-*.zip`** 拖入管理器，检查安装预览：JamieWin 的脚本、播放器、音频和配置应全部落在 `platform/steam/ue4ss/Mods/JamieWin` 下，然后安装并启用。
4. 候选版预期从 Steam 正常启动游戏即可，播放器随游戏启动和退出，无需手动运行安装或播放脚本；这一自动启动流程仍待实机验收。

加载器作为公共前置单独管理，分享 JamieWin 时提供 **ModOnly 包**。不要将包含加载器的 Full 包作为 JamieWin 的常规更新包导入。

已有手动安装的 JamieWin 时，先备份原 JamieWin 文件夹和音量设置，退出游戏及旧播放器，再将原 JamieWin 文件夹移出游戏目录后通过管理器安装。此后更新也通过管理器进行，避免直接覆盖其管理的文件。管理器迁移流程同样待验证。

## 手动解压安装

不使用管理器时，0.8 候选包也提供手动解压方式：

1. 完全退出游戏。通过 Steam 的「管理 → 浏览本地文件」打开 PBZ 游戏根目录。
2. **已有兼容 UE4SS：使用 ModOnly 包。** 将 ZIP 内的 `platform` 文件夹合并进 PBZ 根目录。
3. **从未安装 UE4SS：可使用 Full 包。** 它包含适配加载器，仅用于首次安装；已有加载器时使用 ModOnly 包，保留共用设置与其他 Mod。
4. 检查以下目录结构。不要额外套一层压缩包名称文件夹，也不要把本 Mod 放到 `~mods` 中。

```text
<PBZ 游戏目录>/
└─ platform/steam/
   ├─ PBZ.exe                         游戏原文件
   ├─ dwmapi.dll                      UE4SS 加载入口
   └─ ue4ss/
      ├─ UE4SS.dll
      └─ Mods/
         └─ JamieWin/
            ├─ Scripts/
            ├─ Player/JamieWin.Audio.exe
            ├─ Audio/
            ├─ runtime/
            ├─ audio.json
            └─ enabled.txt
```

JamieWin 的文件集中在自己的模组目录。首次安装加载器会在游戏程序旁新增加载入口，后续安装、更新 JamieWin 只涉及自己的目录。更新前备份 `audio.json` 中的音量设置。

## 音量设置

0.8 候选包的配置位于 `<PBZ 游戏目录>/platform/steam/ue4ss/Mods/JamieWin/audio.json`。完全退出游戏后编辑，下一次启动生效。数值范围为 `0`（静音）到 `1`（最大音量）：

| 设置 | 默认值 | 作用 |
| --- | --- | --- |
| `MusicVolume` | `0.45` | 两首背景音乐的音量 |
| `DrinkVolume` | `0.9` | 杰米四酒音效的音量 |
| `WinVolume` | `1.0` | Jamie wins 的音量 |
| `DuckVolume` | `0.2` | 音效或语音播放期间，Mod 背景音乐暂时降低到的音量 |

## 停用、更新与卸载

- **通过管理器安装：** 完全退出游戏后，在管理器中停用、更新或卸载 JamieWin。管理器的完整操作流程尚待本 Mod 实测。
- **手动解压安装：** 完全退出游戏及播放器，暂时停用可将 JamieWin 文件夹移出 `ue4ss/Mods`；卸载可删除该文件夹；更新只处理自己的 JamieWin 文件夹，并保留音量设置。
- **使用旧版手动启动的播放器：** 先使用旧包的停止入口退出播放器，再进行迁移或卸载。

使用其他 UE4SS Mod 时，请保留共用的 `dwmapi.dll`、`UE4SS.dll` 和其他 Mod。通过管理器安装的加载器也应由管理器管理。

## 技术文档

源码安装、构建与测试命令、日志位置和既有验证记录见 [开发与技术说明](development.md)。源码目录与面向玩家的 ModOnly 安装包用途不同，分享时应提供构建后的包。

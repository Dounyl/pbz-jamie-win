# JamieWin · 影之刃零醉剑音频 Mod

清醒持醉剑时播放《Mr.Top.Player》，微醺或大醉时切换《鸳鸯戏》，并配上杰米四酒日语音效和处决开始 2 秒后的「Jamie wins」。

当前版本：**1.1.0**。通过 **UEMM（UE MM）** 安装，装好后正常进游戏就能用。

《Mr.Top.Player》比 1.0.1 再提高 20%；四酒和「Jamie wins」音效直接叠加，背景音乐保持原有音量和播放进度。继续使用原始 M4A / MP3 小体积安装包。

## 安装

**UEMM 下载地址：[官方发布页](https://github.com/KintaroModding/uemodmanager/releases)**

1. 先退出游戏。
2. 下载 UEMM，解压后运行 `UEModManager.exe`。如果没有自动找到游戏，在设置里选游戏目录。
3. 在 UEMM 的 **UE4SS** 页面安装适配游戏的 UE4SS。已经装过兼容版本就跳过。
4. 把 **`JamieWin-1.1.0.zip`** 拖进 UEMM，确认名称是 **JamieWin**、版本是 **1.1.0**，安装并启用。
5. 从 Steam 正常启动游戏。

ZIP 直接导入即可，不用手动解压，也不用运行仓库里的 PowerShell 脚本或外部播放器。

安装预览里的文件应放在 `platform/steam/ue4ss/Mods/JamieWinNativeAudioTest/`。文件夹沿用旧名字，方便更新。

已验证环境：Windows x64、PBZ Steam build `26266538`、UE4SS `v3.0.1-1195-g1ceefac8`。其他版本还没测过。UEMM 的使用方法见[官方说明](https://github.com/KintaroModding/uemodmanager/blob/main/openmods.md)。

## 怎么播放

| 游戏中的状态或动作 | 播放内容 |
| --- | --- |
| 清醒且实际手持醉剑 | 循环《Mr.Top.Player》；只放在背包里不触发 |
| 微醺或大醉 | 循环《鸳鸯戏》 |
| 微醺和大醉之间切换 | 同一首继续，不重头播放 |
| 每次新进入大醉 | 四酒日语音效一次 |
| 醉剑成对处决动画实际开始，目标仍存活 | 延迟 2 秒播放一次「Jamie wins」；普通重击和可处决提示不触发 |
| 恢复清醒仍持醉剑 | 切回《Mr.Top.Player》 |
| 清醒收剑／换武器 | 停止 Mod 音乐，恢复游戏原配乐 |
| 死亡、无玩家、标题界面 | 停止音乐和语音，恢复原配乐 |
| 打开暂停、设置或系统菜单 | 音乐继续，声音逐渐变闷；语音暂停 |
| 退出菜单继续游戏 | 音乐恢复清晰，不从头播放；语音继续 |
| F10 | 本次游戏停用 Mod，恢复原配乐；重启游戏后重新启用 |

读档时如果已经大醉，不会补播四酒语音。Mod 只改声音，不改角色数值、战斗和存档。

## 调音量

直接用游戏里的音量设置：

- **音乐音量**控制两首背景音乐。
- **对话／语音音量**控制四酒和「Jamie wins」。
- **总音量**控制全部声音。

播放语音或音效时，Mod 背景音乐保持音量和进度，不会被压低、暂停或重播。调音量不会让歌曲重播，收剑后原配乐按你最新设置的音量恢复。

## 更新、停用和卸载

先退出游戏，再到 UEMM 里选中 JamieWin 操作：

- **更新**：用新的 ZIP 更新现有条目。
- **停用或卸载**：使用 UEMM 里的对应操作。

同时只启用一个 JamieWin 版本。用过旧的外部播放器版，要先停用旧版并关闭播放器。

## 遇到问题

反馈时说一下做了什么、听到了什么，并附上这些日志：

- Mod 文件夹下 `runtime/` 里的 `native-audio-test.log`、`native-output.log` 和 `native-status.txt`。
- `platform/steam/ue4ss/UE4SS.log`。

## 源码与构建

以下内容供开发使用，玩家按上面的 UEMM 步骤安装即可。

当前实现位于 `probes/JamieWinNativeAudioTest/`，共享原有 `core.lua`、`weapon.lua` 和 `settings.lua`。在项目根目录执行：

```powershell
& ./tools/build-native-audio-test.ps1
python tests/test_native_audio_probe.py
python tests/test_native_menu_detection.py
python tests/test_lua.py
python tests/test_native_mixer.py
python tests/test_native_audio_decode.py
python tests/test_native_menu_preview.py
python tests/test_native_audio_device.py
& ./tools/package-native-audio-test.ps1
```

构建依赖项目缓存中的 Zig 0.13.0 和 FFmpeg，Lua 检查使用 `.local/cache/testdeps` 中的 Lupa。两首音乐直接复制原始文件，由 Windows Media Foundation 在进程内解码，FFmpeg 只用于构建语音 PCM 和离线参考检查。构建脚本支持显式传入编译器和 FFmpeg 路径。产物仅写入 `.local/`；设备检查只播放生成的静音数据，音乐解码与混音检查离线运行，不安装或操作游戏。

实现和测试记录见 [开发记录](docs/native-audio-probe.md)。[旧外部播放器版说明](docs/legacy-external-player.md)仅供查阅，不适用于当前版本。

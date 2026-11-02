# GitHub Release 打包

`Build release` 在 GitHub 的 Windows 环境中构建安装包。工作流发布时只使用对应标签的源码，版本必须与 `probes/JamieWinNativeAudioTest/mod.json` 一致。

## 发布新版本

1. 更新元数据、Lua 和 DLL 的版本，提交并推送代码。
2. 为该提交创建 `v主版本.次版本.补丁版本` 标签，并发布 GitHub Release。
3. `Build release` 自动安装固定版本的构建依赖，打包并运行离线回归检查。
4. 检查通过后，工作流上传 `JamieWin-版本.zip` 和对应的 `.sha256` 文件，并更新 Release 说明中的校验值。

## 为已有 Release 补包

在仓库 **Actions → Build release → Run workflow** 中选择 `main`，填写已有 Release 的标签，例如 `v1.0.0`。工作流从 `main` 读取最新构建流程，从指定标签读取待发布源码，因此可为加入工作流之前的版本补包。

重新运行会替换同名附件，发布说明中的其他内容保留。构建时间会影响 ZIP 和 DLL 的字节内容，每次构建以新生成的 SHA256 为准。

## 构建与验证范围

- Windows x64，Python 3.13、Zig 0.13.0、imageio-ffmpeg 0.7.0、Lupa 2.8。
- 复用 `tools/package-native-audio-test.ps1`，包含 DLL 编译、PCM 转换和 ZIP 打包。
- 检查 Lua 状态与菜单检测、原生混音、离线菜单音效、包内文件和版本一致性、ZIP 完整性及 SHA256。
- 上传使用当前仓库的临时 `GITHUB_TOKEN`，无需本机登录或另建个人访问令牌。

云端检查不包含真实游戏或音频设备验收。实际运行结果见 Actions 日志；成功后 Release 的 Assets 中应出现安装 ZIP 和 SHA256 文件。

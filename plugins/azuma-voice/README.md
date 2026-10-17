# 冬雪莲语音回复（azuma-voice）

QQ Agent 0.4.8.5 的语音发送适配插件。依赖仓库根目录的本地 GPT-SoVITS v2Pro 服务。

完整安装、模型配置、隐私说明请阅读 [项目 README](https://github.com/QinYooo/qq-agent-gpt-sovits-voice#readme)。
单独复制此目录到 QQ Agent 后，请回 GitHub 仓库查看完整说明。

- 插件设置 `sovitsDir` 必须填写语音项目绝对路径，默认留空。
- 推荐用完整项目的 `install-plugin.bat` / `install-plugin.sh` 安装，自动根据脚本位置填写路径；升级时会先备份。
- 安装生成的本地 `installation.json` 在首次可信加载时同步旧的已保存路径，后续手动 UI 调整保留；该文件不要提交。
- Windows 与 Linux 分别启动 `.venv/Scripts/python.exe` 和 `.venv/bin/python`，设备读取 `voice.json`。
- `/voice on`：当前群或私聊开启纯语音；`/voice off`：恢复文字；`/voice`：查看状态。
- 开关保存在 QQ Agent 的插件数据目录；首次安装默认文字。
- 服务固定访问 `127.0.0.1:9881`，不会接受群消息中的网址。
- 读取本地文件和启动 Python 需要 QQ Agent 的单插件信任；只信任 `azuma-voice`。
- 使用可恢复的 `SendQueue.sendTextBatch` 适配；没有修改 QQ Agent 核心文件。
- 依赖 `src/sender.js`、`src/config.js`、`src/skills/config.js`、`store.findByMid` 等内部接口，升级框架后需复核。
- 语音合成失败、超长、队列满时回退原文字；明确的 Highway 上传失败触发该会话两分钟冷却。
- 无法确认是否已发送的网络错误会抛出，不自动补发，避免重复消息。

完整项目的 setup 脚本可在使用者本机下载默认角色权重与参考音频；聊天模型 API 与 QQ 登录仍需自行配置。本插件不提供角色人设或记忆库。

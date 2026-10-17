# QQ Agent + GPT-SoVITS 本地语音回复

把 QQ Agent 生成的聊天回复转换成本地角色语音。支持按群或私聊切换文字 / 纯语音，模型常驻内存，语音失败时回退文字。

本项目使用 **GPT-SoVITS v2Pro** 推理后端。项目名里的 TTS 表示文字转语音；它没有使用另一个名为 ChatTTS 的模型项目。只发布语音服务与 `azuma-voice` 插件，不包含 QQ 机器人本体、聊天模型、人设或记忆插件。

**仓库和 Release 不附带任何模型权重、参考音频、账号信息或可直接使用的私人配置。** 使用者需要自行完成下面的模型与 QQ Agent 配置。

[下载发布包](https://github.com/QinYooo/qq-agent-gpt-sovits-voice/releases/latest)：首次安装选完整源码包；已有本项目语音服务时可只取 `azuma-voice` 插件包。

## 已验证环境与功能

- Windows、Python 3.11、PyTorch / torchaudio 2.8.0 + CUDA 12.6。
- NVIDIA RTX 4070 12GB；性能会随模型、句长及硬件变化。
- QQ Agent **0.4.8.5** + SnowLuma **1.14.22**。其他版本未验证。
- `/voice on` 开启当前会话纯语音；`/voice off` 恢复文字；`/voice` 查看状态。
- 各会话开关独立且重启保留；开关确认始终发送文字。
- 语音合成串行排队，队列最多容纳 4 个请求；超过 600 字、无可朗读正文、队列满或合成失败时回退原文字。
- QQ 明确报告语音上传失败时回退文字，该会话冷却 2 分钟；再次 `/voice on` 可立即重试。无法确认是否送达的超时不会盲目补发。

插件跟随 QQ Agent 原本的聊天触发规则。它负责回复的发送形式，不负责决定何时接话，也不替代聊天模型。

## 1. 准备语音环境

先安装 [Python 3.11](https://www.python.org/downloads/)、[Git](https://git-scm.com/downloads) 和可支持 CUDA 12.6 运行时的 NVIDIA 驱动。将本仓库下载 / 解压到普通本地目录，然后在该目录打开 PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

`python` 不是 3.11 时，明确指定解释器：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Python "D:\Python311\python.exe"
```

脚本会创建 `.venv`、安装固定版本依赖、获取固定版本 [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) 源码，并下载 BERT、CNHuBERT、说话人编码器、G2PW 和 NLTK 等共享资源。**这些资源同样是下载到使用者本地，不包含在本仓库中。** 初次安装需数 GB 下载量和足够磁盘空间。首次创建的 `voice.json` 是配置模板，还不能直接合成。

安装不会自动下载角色权重或参考语音，也不会覆盖已有 `voice.json`。依赖版本记录在 `requirements.lock.txt`；不要把固定版本的上游目录替换为不同版本后直接沿用此环境。

## 2. 自行准备角色权重与参考语音

需要一对相互兼容的 **v2Pro** 权重：GPT `.ckpt` 和 SoVITS `.pth`，以及一段 **3–10 秒**、干净且有权使用的参考 WAV。参考音频的准确逐字转写必须与配置一致。

東雪蓮 / 冬雪莲可参考 [Sucial 的社区模型页](https://huggingface.co/Sucial/seren-azuma-gpt-sovits)。已有验证使用的资源版本为 `0763f55fb51e0b4be511c2010abeb1afa896a9a7`，检查点为 `GPT_weights_v2Pro/azuma-e15.ckpt` 与 `SoVITS_weights_v2Pro/azuma_e8_s2928.pth`。这只是已验证组合，不代表最优检查点；本仓库不重新分发该模型或音频。请先阅读模型页及素材来源的许可说明。

推荐本地目录：

```text
项目目录/
  models/voice/gpt.ckpt        # 自行准备的 GPT 权重
  models/voice/sovits.pth      # 自行准备的 SoVITS v2Pro 权重
  references/default.wav      # 自行准备的参考语音
  voice.json                  # 由 voice.example.json 复制后编辑
```

可以直接使用模型原文件名，只需同步修改 `voice.json`。没有运行安装脚本时，先复制模板：

```powershell
Copy-Item .\voice.example.json .\voice.json
```

编辑 `voice.json`：

| 字段 | 填写内容 |
|---|---|
| `repo_dir` | 固定上游源码目录，通常保留 `vendor/GPT-SoVITS` |
| `gpt_weights` / `sovits_weights` | 自己的权重路径，可相对本仓库根目录或使用绝对路径 |
| `reference_audio` | 参考 WAV 路径 |
| `reference_text` | 参考语音的准确转写，不能保留模板占位文字 |
| `reference_language` | 中文参考通常为 `all_zh` |
| `text_language` | `zh` 适合中文夹杂英文；`all_zh` 为纯中文 |
| `speed` | 0.5–2.0，默认 1.0 |

完成后检查并单独生成一次：

```powershell
.\.venv\Scripts\python.exe tts.py --check
.\.venv\Scripts\python.exe tts.py --text "你好，今天过得怎么样？" --output outputs\hello.wav --play
```

`--output` 后需要文件名；省略整个选项会自动生成文件名。双击 `run_tts.bat` 可连续输入，`/quit` 退出。独立 CLI 支持 `--device cpu`，速度与显存表现需自行评估；插件自动启动路径默认使用 CUDA。

## 3. 安装 QQ Agent 语音插件

先按 QQ Agent 自身说明完成 QQ 登录、聊天模型 API 和文字聊天测试。本仓库不附带这些配置。

**自动复制（常规 Windows 安装位置）：**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-plugin.ps1
```

自定义安装位置时，`AgentPath` 应指向同时包含 `src/`、`plugins/` 的应用目录：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-plugin.ps1 -AgentPath "D:\Apps\QQ Agent\resources\app"
```

安装脚本仅复制 `plugins/azuma-voice`，并为复制后的插件写入当前语音项目路径；不会修改 QQ 登录、模型 API、主人名单或信任列表。已有同名插件时会停止，避免覆盖，请先自行备份旧插件。

**手动安装：** 把本仓库的 `plugins/azuma-voice` 整个目录复制到 QQ Agent 实际的 `plugins/` 下。Electron 安装版通常位于 `%LOCALAPPDATA%\Programs\QQ Agent\resources\app\plugins\`，请以发行版的扩展文档为准。

回到 QQ Agent 的「插件」页，应看到「冬雪莲语音回复」。该插件为自动启动本地 Python 使用文件与子进程能力，需要在 QQ Agent 显示拦截时选择**仅信任 `azuma-voice` /「信任并重试」**。请先审阅源码；不要关闭全局安全检查或信任其他无关插件。

在插件设置中确认「本地 GPT-SoVITS 语音项目目录」是本仓库根目录的**绝对路径**，其中包含 `tts_server.py`、`voice.json`、`.venv`。手动安装默认路径留空，必须填写。旧版残留的已保存设置会优先于默认值，也需要核对。

保持「自动启动」开启时，插件会加载本地模型。群里必要时先 @机器人发送：

```text
/voice on
你好，今天有什么有意思的事？
/voice off
这句应该以文字回复。
```

首次模型加载会慢一些。该群开语音不影响其他群或私聊；默认所有会话均为文字。开关命令目前未额外限制主人权限，应结合 QQ Agent 自身的消息接收范围使用。

## 4. 手动启动服务与接口

需要自己管理进程时，在插件中关闭「自动启动」，单独运行：

```powershell
.\.venv\Scripts\python.exe tts_server.py
```

- `GET http://127.0.0.1:9881/health`：就绪状态。
- `POST http://127.0.0.1:9881/tts`：`Content-Type: application/json`，请求体 `{"text":"你好"}`，返回完整 WAV。
- 固定监听回环地址，拒绝带 `Origin` 的浏览器请求；无需密钥，供同机可信进程使用。不要映射到公网。
- 最多 600 字，完整合成后返回，当前没有流式播放。
- SnowLuma 将 WAV 转为 QQ 可用的 SILK；插件经 QQ Agent 的发送队列保留白名单、限频与聊天留档。

也可以复用 Python 类 `VoiceSynthesizer`，实例应常驻并串行调用 `synthesize(text, Path(...))`。

## 故障排查与兼容范围

| 现象 | 检查方向 |
|---|---|
| 插件提示未信任 | 在插件页只信任 `azuma-voice`，然后重试 |
| 提示项目目录不完整 | 检查插件路径、`.venv/Scripts/python.exe`、`tts_server.py` |
| `--check` 缺文件 | 按提示准备角色文件；共享依赖可重跑 `prepare_assets.py` |
| 找不到 CUDA | 检查驱动和安装环境；独立 CLI 可用 `--device cpu` 排查 |
| 已开语音但收到文字 | 检查长度、合成错误、队列和上传冷却；见下方日志 |
| 明确 Highway 上传失败 | 已自动回退文字，2 分钟后恢复；检查 QQ / SnowLuma 网络状态 |
| 热重载后服务未运行 | 下次语音请求会尝试启动；也可等旧进程结束后重新启用插件 |
| 升级 QQ Agent 后失效 | 本插件依赖内部接口，仅验证 0.4.8.5；复核发送队列和 `findByMid` 行为 |

合成详细日志：本项目 `runtime/tts.log`。进程启动日志：QQ Agent 数据目录 `plugin-data/azuma-voice/tts.log`。不要把含聊天内容或本机路径的完整日志直接上传到公开 issue。

当前没有稳定的官方发送前 hook，入口对 `SendQueue.sendTextBatch` 做可恢复适配；禁用 / 卸载时恢复原方法。没有修改 QQ Agent 核心或内置插件。语音长度、音质与发音仍受使用者选用的权重和参考音频影响。

## 开发与发布检查

Node.js 20.3+ 与 Python 3.11+，不需要 GPU 或模型即可运行这些模拟测试：

```powershell
npm test
python -m unittest discover -s tests -p "test_*.py"
python scripts/check_publication.py
```

测试不会登录 QQ 或发送真实消息。发布检查对 Git 纳入的文件执行清单、体积和常见敏感内容检查；忽略的本地配置不会被打包。

源码采用 [MIT License](LICENSE)，上游和模型资源说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。数据边界与发布排除项见 [PRIVACY.md](PRIVACY.md)。

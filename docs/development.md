# 开发与无人值守配置

## 入口与文件职责

| 文件 | 作用 |
|---|---|
| `setup.bat` / `setup.sh` | Windows CMD / Linux Bash 入口，定位脚本目录并选择 Python 3.11 |
| `scripts/setup.py` | 创建 `.venv`、固定上游、选择 PyTorch wheel、安装依赖并检查设备 |
| `scripts/download_voice.py` | 选择角色文件、下载、验证参考时长、生成本地配置 |
| `prepare_assets.py` | 下载固定版本公共推理资源和 NLTK 数据 |
| `install-plugin.bat` / `install-plugin.sh` | 插件安装入口 |
| `scripts/install_plugin.py` | 定位宿主、备份更新插件、生成本次安装元数据 |
| `plugins/azuma-voice/installation.js` | 首次可信加载时同步本插件的已保存项目路径 |
| `tts.py` / `tts_server.py` | 独立合成与回环 HTTP 服务 |

所有 Python 调用以参数数组执行，不通过 shell 拼接执行模型网址。所有入口以脚本位置定位项目；不依赖用户当前目录或手动激活环境。Python / Git 是前置依赖，脚本不会改系统 Python 或驱动。

## 配置参数

Windows CMD 示例，Linux 将 `setup.bat` 换为 `bash setup.sh`：

```bat
setup.bat --dry-run --device cpu --non-interactive
setup.bat --device cu126 --non-interactive
setup.bat --skip-assets --device cpu --non-interactive
setup.bat --assets-only --device cpu --non-interactive
```

- `--dry-run`：显示计划，不下载或修改环境、模型与配置。
- `--skip-assets`：只构建环境，未完成可用语音安装；用于开发与 CI。
- `--assets-only`：复用已装环境，重新下载缺失资源 / 配置角色；不会改变已安装的 PyTorch 构建。
- `--non-interactive`：禁止文件选择输入；默认角色预设可以直接使用。自定义仓库有多个候选时必须给出明确文件。
- `--replace-voice`：替换已有 `voice.json` 前备份到 `.backups/`。不带这个参数时保留现有角色配置，只在设备变化时备份并同步 `device`。

自定义模型的无人值守示例，所有路径均为仓库内路径，需替换为该仓库真实文件名：

```bat
setup.bat --device cu126 --model-url "owner/voice" --revision "main" --gpt-file "GPT_weights_v2Pro/voice.ckpt" --sovits-file "SoVITS_weights_v2Pro/voice.pth" --reference-file "refs/sample.wav" --reference-text "参考语音的准确转写" --non-interactive --replace-voice
```

也支持 `/tree/提交或分支` 形式的 Hugging Face 仓库 URL。下载前把 revision 解析为确定的提交，再以同一提交下载三个文件。默认角色使用固定提交；自定义仓库默认 `main`，建议部署时指定提交。参考文件名的转写推断只是一种便利，使用者仍需核对真实音频内容。模型推理最终会检查实际版本为 v2Pro。

如需通过指定 Python 启动：CMD 先 `set "TTS_PYTHON=D:\Python311\python.exe"`；Bash 用 `TTS_PYTHON=/path/to/python3.11 bash setup.sh`。变量只指定可执行文件，不嵌入参数或命令。

## 插件安装与迁移

```bat
install-plugin.bat --agent-path "D:\Apps\QQ Agent" --non-interactive
install-plugin.bat --agent-path "D:\Apps\QQ Agent" --upgrade --non-interactive
```

Linux：

```bash
bash install-plugin.sh --agent-path /opt/qq-agent --upgrade --non-interactive
```

默认语音项目路径是脚本所属仓库根目录，可用 `--tts-dir` 指向另一个已经配置完成的完整项目。宿主目录可以是安装根目录、`resources/app` 或同时含 `src/sender.js` 与 `src/config.js` 的源码根目录。

安装器不写宿主的账号 / 全局配置 / 信任名单。它写入插件 manifest 的默认路径和本地 `installation.json`。可信插件在 `setup()` 中通过宿主 `setSkillConfig` **只更新 `azuma-voice.sovitsDir`**，用 `api.storage` 记录已应用的部署 generation，解决旧配置优先于新 manifest 默认值的问题。后续热重载不会反复覆盖 UI 的手动设置。升级安装生成新 generation，重新应用迁移路径。

手动只复制 `plugins/azuma-voice` 也可以，此时没有 `installation.json`，需自行填写插件设置。请勿提交本地安装产生的 `installation.json` 或包含绝对路径的 manifest。升级备份保留旧插件文件，不删除聊天记录或开关存储。

## 推理、服务与兼容性

直接调用虚拟环境解释器，Windows 为 `.venv\Scripts\python.exe`，Linux 为 `.venv/bin/python`：

```text
python tts.py --check
python tts.py --text "你好" --output outputs/hello.wav
python tts_server.py
```

上面 `python` 应换为对应虚拟环境解释器。`--device auto` 默认读取 `voice.json.device`（`cuda` / `cpu`）；旧配置未提供时保留 `cuda` 行为。显式 `--device cpu` / `cuda` 仅覆盖当前运行。`VoiceSynthesizer` 可常驻复用，调用必须串行。

- `GET /health` 返回就绪 JSON；`POST /tts` 接受 `{"text":"你好"}` 和 `Content-Type: application/json`，返回完整 WAV。
- 服务只监听 `127.0.0.1:9881`；拒绝浏览器 Origin、不匹配 Host 和超过 600 字的请求。
- 插件固定访问同机回环，不接受群消息中的任意服务地址。
- Windows 启动 `.venv/Scripts/python.exe`，Linux 启动 `.venv/bin/python`；停用时只终止插件自己创建的进程。
- 发送经 QQ Agent 的 `SendQueue`；没有稳定的官方发送前 hook，因此使用可恢复的原型适配。禁用时恢复原方法。
- 依赖 `src/sender.js`、`src/config.js`、`src/skills/config.js` 与 `ChatStore.findByMid`，仅验证 QQ Agent 0.4.8.5。

CUDA 配置参考固定上游安装脚本的索引选择方式：
[GPT-SoVITS install.sh](https://github.com/RVC-Boss/GPT-SoVITS/blob/1b47ca07ef43a284e0b8bd7f29d3e1e3ff76082a/install.sh)、
[PyTorch 2.8 安装说明](https://pytorch.org/get-started/previous-versions/#v280)。本桥接固定 torch / torchaudio 2.8.0，并分离 CPU / CUDA wheel 与公共依赖锁。Flash Attention、Triton 和 CUDA Graph 不是本项目的必要安装步骤；保留关闭加速的已验证推理路径。

## 测试与发布

Node.js 20.3+、Python 3.11，不需要 GPU、模型或 QQ 登录即可运行模拟测试：

```text
npm test
python -m unittest discover -s tests -p "test_*.py"
python scripts/setup.py --dry-run --device cpu --non-interactive
python scripts/check_publication.py
```

CI 分别在 Windows / Linux 运行测试和入口检查，另外在 Ubuntu 构建 CPU 虚拟环境并执行 PyTorch 运算。CI 不下载角色权重，不发送 QQ 消息；Linux 真 QQ 和不同显卡仍需独立集成验证。

发布检查采用严格源文件清单。新增源码后应审查内容，再更新 `scripts/check_publication.py` 的允许清单。Release 从 Git tag 生成，禁止从包含 `.venv`、模型、日志、真实配置的工作目录整体压缩。默认角色来源在脚本中配置，公开文件不包含实际参考 WAV 或用户聊天数据。

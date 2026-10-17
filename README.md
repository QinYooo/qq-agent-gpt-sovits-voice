# QQ Agent + GPT-SoVITS 本地语音回复

让 QQ Agent 把聊天回复转换成本地角色语音。群或私聊中发送 `/voice on` 开纯语音，`/voice off` 恢复文字，各会话开关独立并保留。

**v1.2.0：Windows 用 CMD / 双击批处理，Linux 用 Bash。** 安装脚本会建立虚拟环境、选择 PyTorch CUDA / CPU 构建、安装依赖、下载模型，并生成本机配置。默认角色为東雪蓮 / 冬雪莲，也支持其他兼容的 v2Pro 角色仓库。

[下载完整发布包](https://github.com/QinYooo/qq-agent-gpt-sovits-voice/releases/latest) · [开发者说明](docs/development.md) · [隐私说明](PRIVACY.md)

本项目使用 **GPT-SoVITS v2Pro**，不使用另一个名为 ChatTTS 的模型项目。公开包只有语音服务、语音回复插件、脚本、模板和说明；不附带模型、音频、账号、聊天记录、人设或记忆插件。安装时的资源下载发生在使用者电脑上。

## 新用户：三步完成

### 第一步：准备 Python、Git 和项目

**Windows 10 / 11，64 位：**

1. 安装 [Python 3.11](https://www.python.org/downloads/)，安装时勾选 **Add Python to PATH**；安装 [Git](https://git-scm.com/downloads)。
2. 下载本项目的完整 ZIP，先**全部解压**到一个普通、可写的目录，例如 `D:\QQVoice`。不要在压缩包内直接运行，也不要放进需要管理员权限的系统目录。
3. 使用 NVIDIA 显卡时，先安装适用于该显卡的 NVIDIA 驱动。没有可用 NVIDIA 环境时脚本会选择 CPU，速度通常较慢。

**Linux x86_64：** 准备 Git、Python 3.11、对应的 venv 与 pip 支持。部分发行版构建依赖还需要 GCC / G++ 和 Python 开发头文件。Debian / Ubuntu 可在发行版提供这些包时安装：

```bash
sudo apt install git python3.11 python3.11-venv python3.11-dev build-essential
```

如果系统软件源没有 Python 3.11，请先通过自己信任的 Python / Conda 安装方式准备 3.11。本脚本不会自动改系统 Python、安装显卡驱动或运行 sudo。

首次安装需要数 GB 下载与磁盘空间，可访问 GitHub、PyTorch 官方下载源和 Hugging Face。模型会下载到本机，请先阅读 [默认角色模型说明](https://huggingface.co/Sucial/seren-azuma-gpt-sovits) 与 [资源使用说明](THIRD_PARTY_NOTICES.md)，确认有权使用相应声音和素材。

### 第二步：自动配置语音

**Windows：双击 `setup.bat`**，或在项目目录的 CMD 输入：

```bat
setup.bat
```

**Linux：在解压目录打开终端，运行：**

```bash
bash setup.sh
```

不需要先激活虚拟环境，也不需要手写配置。默认流程会：

1. 创建项目内的 `.venv`，获取固定提交的 GPT-SoVITS 源码。
2. 检测 NVIDIA 驱动和显卡，选择 CUDA 12.6、CUDA 12.8 或 CPU 版 PyTorch，并执行实际张量运算检查。
3. 安装公共推理依赖、BERT、CNHuBERT、说话人编码器、G2PW 和 NLTK 资源。
4. 从默认角色仓库下载已选定的 GPT / SoVITS 权重与参考 WAV，验证参考时长，自动生成 `voice.json`。
5. 检查资源与运行设备，最后显示「安装完成」。

默认预设固定在角色仓库提交 `0763f55fb51e0b4be511c2010abeb1afa896a9a7`，使用 `azuma-e15.ckpt` 与 `azuma_e8_s2928.pth`；参考转写来自仓库发布的中文 WAV 文件名。这是已验证的起始组合，不代表最优检查点。

安装中断后可重跑同一命令，下载缓存会尽量复用。**已有 `voice.json` 会保留**；升级旧项目但仍是占位配置时，请运行 `setup.bat --replace-voice` 或 `bash setup.sh --replace-voice`，原配置会先备份到 `.backups/`。

想先听一句：Windows 双击 `run_tts.bat`，输入文字回车；Linux 运行 `bash run_tts.sh`。输入 `/quit` 结束。独立测试生成的 WAV 保存在 `outputs/`；Windows 自动播放，Linux 可用自己的播放器打开。

### 第三步：安装 QQ Agent 插件

先在 QQ Agent 中完成 QQ 登录、聊天模型 API 配置，并确认文字聊天正常。本项目不提供这些账号配置。

**Windows：双击 `install-plugin.bat`**，常规安装位置会自动识别；未找到时按提示粘贴 QQ Agent 安装目录。也可以在 CMD 指定：

```bat
install-plugin.bat "D:\Apps\QQ Agent"
```

**Linux：**

```bash
bash install-plugin.sh "/opt/QQ Agent"
```

支持传程序安装目录，或直接传包含 `src/` 的 QQ Agent 源码目录。Linux AppImage 内只读目录不能直接写入，请使用可写的应用源码 / 解包目录；宿主仍需自己具备可用的 QQ / OneBot 环境。

安装脚本会把 `azuma-voice` 放入实际 `plugins/`，并**根据安装脚本所在的完整项目目录**填写语音路径，与你从哪个工作目录运行无关。首次可信加载时，插件会同步自己已保存的旧路径；之后你在插件页手动调整仍有效。移动整个语音项目后，从新位置重跑插件安装并选择升级即可。

回到 QQ Agent 的「插件」页，应看到「冬雪莲语音回复」。如果显示因文件 / 进程能力被拦截，请先审阅源码，再**只对 `azuma-voice` 选择「信任并重试」**。脚本不会代替你修改信任名单，也不会改 QQ 登录、聊天 API 或其他插件。

在 QQ 里发送以下内容测试，群聊根据 QQ Agent 触发规则可能需要 @机器人：

```text
/voice on
你好，今天过得怎么样？
/voice off
这次应该收到文字。
```

首次加载模型会慢一些。语音合成失败、超过 600 字、没有可朗读正文或队列满时回退原文字。QQ 明确报告语音上传失败时，该会话冷却 2 分钟；再次 `/voice on` 可重试。无法确定是否送达的网络错误不会盲目补发。

## CUDA / CPU 怎么选

默认自动检测。与上游安装方式一致，从 [PyTorch 官方对应索引](https://pytorch.org/get-started/previous-versions/#v280) 安装固定版本 `torch` / `torchaudio`。推理用的 PyTorch wheel 携带相应 CUDA 运行时，**通常不需要另装系统 CUDA Toolkit**，但 NVIDIA 驱动必须支持所选构建。

| 选择 | Windows CMD | Linux Bash |
|---|---|---|
| 自动，默认 | `setup.bat` | `bash setup.sh` |
| CUDA 12.6 | `setup.bat --device cu126` | `bash setup.sh --device cu126` |
| CUDA 12.8 | `setup.bat --device cu128` | `bash setup.sh --device cu128` |
| CPU | `setup.bat --device cpu` | `bash setup.sh --device cpu` |

一般已支持的 NVIDIA 显卡优先 CUDA 12.6；检测到需要较新构建的显卡时选择 CUDA 12.8。检测结果不等于完整的硬件兼容认证，安装后还会尝试一次 CUDA 运算。显式要求 CUDA 但不可用时会报错，不会悄悄更换为 CPU。

设备选择会写进新生成的 `voice.json`，独立脚本和插件自动启动都读取它。若已有配置被保留，里面的 `device` 也会保留；切换已有配置的运行设备请把该字段改为 `cpu` 或 `cuda`，或在确认更换角色配置时使用 `--replace-voice`。切换 PyTorch 构建可能触发较大的重新下载。

此版本提供 Windows / Linux x86_64 的 NVIDIA / CPU 安装路径；不提供 AMD ROCm、Apple MPS、ARM 或 v2ProPlus 安装预设。

## 更换角色：提供模型页面链接

目前接受 **Hugging Face 模型仓库页面链接或 `作者/仓库`**，需要 GPT-SoVITS **v2Pro** 权重；网页链接不代表任意模型格式都兼容。例子中的 `作者/模型仓库` 请换为真实仓库。

Windows CMD：

```bat
setup.bat --model-url "https://huggingface.co/作者/模型仓库" --replace-voice
```

Linux Bash：

```bash
bash setup.sh --model-url "https://huggingface.co/作者/模型仓库" --replace-voice
```

其他仓库存在多个权重时，会列出编号让你选择 GPT、SoVITS 和参考 WAV；参考文字可确认中文文件名推断值，或输入准确的逐字转写。没有可靠转写时会要求输入。参考音频需 3–10 秒，默认语言按中文配置；日文等其他语言需同步修改 `reference_language` 和 `text_language`。

默认角色直接下载预设文件，不需做这些选择。脚本仅下载所选的三个角色文件；不会复制整个角色仓库或训练集。它不支持直接下载链接、网盘链接、私有 token 写进 URL，或自动解压任意角色压缩包。其他来源可手动准备权重 / WAV，再参照 `voice.example.json` 配置 `voice.json`。

## 升级、检查与常见问题

下载新版本到新目录，完成 `setup` 后再运行 `install-plugin`，已存在的同名插件会询问是否先备份再升级。非交互更新用 `install-plugin.bat --upgrade` 或 `bash install-plugin.sh --upgrade`。备份位于 QQ Agent 应用目录 `plugin-backups/`；群聊开关保存在 QQ Agent 数据目录中，不随插件源码更新而删除。

| 现象 | 处理方法 |
|---|---|
| 一闪而过或文件找不到 | 全部解压；使用根目录的 `.bat` / `.sh`，不要只复制某一个入口 |
| 找不到 Python 3.11 | 安装 3.11 并加 PATH；开发者可设置 `TTS_PYTHON` 为解释器完整路径 |
| Linux 无法创建 venv / 编译扩展 | 安装对应 venv、Python 开发头文件及 GCC / G++；查看失败包的错误 |
| 下载失败 | 检查对应 GitHub、PyTorch 或 Hugging Face 连通性，恢复后重跑；不要在公开 issue 贴 token |
| CUDA 检查失败 | 更新显卡驱动，或显式 `--device cpu` 安装；不要混用不同项目的 Python 环境 |
| 仍提示占位转写或缺角色文件 | 确认是在新目录安装；旧模板配置可用 `--replace-voice` 备份后重新生成 |
| 提示不能覆盖已有插件 | 选择备份升级，或显式添加 `--upgrade` |
| 插件未加载 | 在插件页只信任此插件；确认 QQ Agent 版本和可写安装目录 |
| 已开语音但收到文字 | 检查超长、合成错误、队列和 QQ 上传冷却状态 |

日志：语音项目 `runtime/tts.log`，QQ Agent 数据目录 `plugin-data/azuma-voice/tts.log`。本地语音服务仅监听 `127.0.0.1:9881`，不要映射到公网。

Windows 设备与模型推理验证基于 RTX 4070、Python 3.11、PyTorch 2.8.0 + CUDA 12.6。QQ Agent 接口验证基于 **0.4.8.5 / SnowLuma 1.14.22**。Linux 提供安装与进程适配，自动检查覆盖脚本、环境与模拟插件；不表示已在 Linux 真 QQ 环境完成语音收发验证。框架升级后需重新核对内部发送接口。

源码采用 [MIT License](LICENSE)，模型、语音素材和第三方依赖适用各自许可，见 [资源说明](THIRD_PARTY_NOTICES.md)。

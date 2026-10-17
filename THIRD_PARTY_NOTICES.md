# 上游与资源来源

本仓库的桥接代码、插件和文档采用 MIT License。此许可不覆盖使用者自行下载的模型、语音素材或第三方依赖。

| 项目或资源 | 使用方式 | 来源 |
|---|---|---|
| GPT-SoVITS | 使用者安装时克隆，保留上游 LICENSE；不随本仓库分发源码或权重 | https://github.com/RVC-Boss/GPT-SoVITS |
| QQ Agent | 插件运行宿主；不随仓库分发 | 安装包声明项目地址：https://github.com/Kondius/qq-agent （发布整理时该地址不可访问，请以所用发行版为准） |
| BERT / CNHuBERT / 说话人编码器 | 使用者运行准备脚本后从上游下载至本地 | https://huggingface.co/lj1995/GPT-SoVITS |
| G2PW | 使用者运行准备脚本后从上游下载至本地 | https://huggingface.co/XXXXRT/GPT-SoVITS-Pretrained |
| 東雪蓮社区微调模型 | README 中的可选示例；由使用者自行获取 | https://huggingface.co/Sucial/seren-azuma-gpt-sovits |
| Python / PyTorch / FFmpeg 及其他依赖 | 从各自发行渠道安装，适用各自许可证 | 见 requirements*.txt 及对应包的元数据 |

上游模型仓库的许可标记不代表本项目拥有角色、声音、参考素材的全部权利。本项目不提供角色官方授权声明，也不重新许可这些资源。使用前请阅读各来源的许可与使用说明，并选择有权使用的声音和素材。

本仓库不包含训练集、参考语音、生成样例音频、模型权重或 QQ Agent 私有配置。

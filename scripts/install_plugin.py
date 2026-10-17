"""Install only azuma-voice; anchor TTS settings to this script's project root."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_FILES = ['plugin.json', 'index.js', 'engine.js', 'worker.js', 'installation.js', 'README.md']


def find_app(path):
    path = Path(str(path).strip().strip('"')).expanduser().resolve()
    for candidate in [path, path / 'resources/app', path / 'app']:
        if (candidate / 'src/sender.js').is_file() and (candidate / 'src/config.js').is_file():
            return candidate
    raise ValueError('所选目录没有 QQ Agent 的 src/sender.js。可选择程序安装目录，或包含 src/ 的源码目录。')


def detect_app():
    candidates = []
    if os.environ.get('QQ_AGENT_APP_DIR'):
        candidates.append(Path(os.environ['QQ_AGENT_APP_DIR']))
    if os.name == 'nt' and os.environ.get('LOCALAPPDATA'):
        candidates.append(Path(os.environ['LOCALAPPDATA']) / 'Programs/QQ Agent')
    candidates.extend([ROOT.parent / 'qq-agent', Path.home() / 'qq-agent', Path('/opt/QQ Agent')])
    found = []
    for candidate in candidates:
        try:
            app = find_app(candidate)
            if app not in found:
                found.append(app)
        except ValueError:
            pass
    return found[0] if len(found) == 1 else None


def install(app, tts_root=ROOT, *, upgrade=False):
    app = find_app(app)
    tts_root = Path(tts_root).resolve()
    if not (tts_root / 'tts_server.py').is_file():
        raise ValueError('语音项目目录必须包含 tts_server.py。')
    python = tts_root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file() or not (tts_root / 'voice.json').is_file():
        raise ValueError('请先在完整项目目录中运行 setup，生成 .venv 和 voice.json，再安装插件。')
    source = ROOT / 'plugins/azuma-voice'
    for name in PLUGIN_FILES:
        if not (source / name).is_file():
            raise ValueError('发布包不完整，请下载完整源码包重新解压。')
    plugins = app / 'plugins'
    if plugins.is_symlink() or (plugins.exists() and plugins.resolve().parent != app):
        raise ValueError('plugins 目录不能链接到应用目录以外。')
    plugins.mkdir(exist_ok=True)
    target = plugins / 'azuma-voice'
    if target.is_symlink() or target.resolve().parent != plugins.resolve():
        raise ValueError('azuma-voice 的安装目标不是应用 plugins 下的普通目录。')
    backup = None
    if target.exists():
        if not upgrade:
            raise FileExistsError('检测到已有插件。升级请添加 --upgrade，或在交互提示中确认；旧插件会先备份。')
        if not target.is_dir():
            raise ValueError('同名目标不是目录，无法安装。')
        backups = app / 'plugin-backups'
        if backups.is_symlink():
            raise ValueError('插件备份目录不能是符号链接。')
        backups.mkdir(exist_ok=True)
        backup = backups / ('azuma-voice-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        shutil.copytree(target, backup, symlinks=True)
    target.mkdir(exist_ok=True)
    manifest = json.loads((source / 'plugin.json').read_text(encoding='utf-8-sig'))
    manifest['settings']['sovitsDir'] = str(tts_root)
    manifest['configSchema']['sovitsDir']['default'] = str(tts_root)
    # The deployment file is local only, excluded from source and release archives.
    # On first trusted load its generation updates just this plugin's saved path.
    deployment = {'version': 1, 'generation': uuid4().hex, 'projectDir': str(tts_root)}
    def atomic_text(path, value):
        temporary = path.with_name(path.name + '.installing')
        temporary.write_text(value, encoding='utf-8')
        os.replace(temporary, path)
    atomic_text(target / 'installation.json', json.dumps(deployment, ensure_ascii=False, indent=2) + '\n')
    for name in PLUGIN_FILES:
        if name in {'plugin.json', 'index.js'}:
            continue
        atomic_text(target / name, (source / name).read_text(encoding='utf-8-sig'))
    atomic_text(target / 'plugin.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    atomic_text(target / 'index.js', (source / 'index.js').read_text(encoding='utf-8-sig'))
    return target, backup


def main(argv=None):
    parser = argparse.ArgumentParser(description='安装 QQ Agent 语音插件并自动填写当前项目路径。')
    parser.add_argument('agent', nargs='?', help='QQ Agent 安装目录或 app 源码目录')
    parser.add_argument('--agent-path', help='与位置参数作用相同')
    parser.add_argument('--tts-dir', default=str(ROOT), help='默认为安装脚本所在的完整项目目录')
    parser.add_argument('--upgrade', action='store_true', help='备份并更新已安装的同名插件')
    parser.add_argument('--non-interactive', action='store_true')
    args = parser.parse_args(argv)
    app = args.agent_path or args.agent or detect_app()
    if not app:
        if args.non_interactive:
            parser.error('未自动找到唯一 QQ Agent 目录，请传入 --agent-path')
        app = input('请粘贴 QQ Agent 安装目录（或包含 src 的源码目录），回车确认：').strip()
    app = find_app(app)
    if (app / 'plugins/azuma-voice').exists() and not args.upgrade and not args.non_interactive:
        args.upgrade = input('已安装 azuma-voice。先备份再升级？输入 y 确认：').strip().lower() == 'y'
    target, backup = install(app, args.tts_dir, upgrade=args.upgrade)
    print(f'插件已安装：{target}\n语音项目路径：{Path(args.tts_dir).resolve()}')
    if backup:
        print(f'旧插件备份：{backup}')
    print('下一步：打开 QQ Agent 插件页，仅对 azuma-voice 选择「信任并重试」。首次可信加载会同步本插件的项目路径。')
    print('在 QQ 中发送 /voice on 并聊天测试；/voice off 恢复文字。移动项目后，请从新位置重跑安装脚本并选择升级。')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    try:
        main()
    except (OSError, ValueError, EOFError) as error:
        print(f'插件未完成安装：{error}', file=sys.stderr)
        raise SystemExit(1)

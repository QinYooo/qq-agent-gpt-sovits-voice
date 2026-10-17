"""Shared installer for setup.bat / setup.sh; runs with standard Python 3.11."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = 'https://github.com/RVC-Boss/GPT-SoVITS.git'
COMMIT = '1b47ca07ef43a284e0b8bd7f29d3e1e3ff76082a'
DEFAULT_MODEL = 'https://huggingface.co/Sucial/seren-azuma-gpt-sovits'
TORCH_VERSION = '2.8.0'
PROBE = """import json, torch
device = __import__('sys').argv[1]
if device == 'cuda':
    assert torch.cuda.is_available(), 'CUDA is not available; check the NVIDIA driver or rerun setup with --device cpu'
    x = torch.ones(16, device='cuda')
    assert (x + x).sum().item() == 32
    torch.cuda.synchronize()
print(json.dumps({'torch': torch.__version__, 'cuda': torch.version.cuda, 'device': device}))
"""


def venv_python(root=ROOT, system=None):
    return root / '.venv' / ('Scripts/python.exe' if (system or os.name) == 'nt' else 'bin/python')


def choose_device(requested, banner='', capabilities=''):
    """CUDA in nvidia-smi is the driver's supported maximum, not the toolkit."""
    if requested != 'auto':
        return requested
    match = re.search(r'CUDA Version:\s*(\d+)\.(\d+)', banner)
    if not match:
        return 'cpu'
    maximum = tuple(map(int, match.groups()))
    caps = [float(value) for value in re.findall(r'^\s*(\d+\.\d+)\s*$', capabilities, re.M)]
    # Newer architectures (e.g. Blackwell) need the newer wheel, even if an
    # older CUDA wheel can initialize the driver successfully.
    modern = (caps and max(caps) >= 10) or bool(re.search(r'RTX\s*(?:50\d\d|PRO\s+\d+.*Blackwell)|\bB[12]00\b', banner, re.I))
    if modern:
        if maximum < (12, 8):
            raise RuntimeError('This GPU needs cu128; update the NVIDIA driver or explicitly select --device cpu.')
        return 'cu128'
    return 'cu126' if maximum >= (12, 6) else 'cpu'


def detect_device(requested):
    if requested != 'auto':
        return requested
    try:
        banner = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=15, check=False).stdout
        caps = subprocess.run(['nvidia-smi', '--query-gpu=compute_cap', '--format=csv,noheader'],
                              capture_output=True, text=True, timeout=15, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        banner, caps = '', ''
    return choose_device(requested, banner, caps)


def dependency_commands(python, device, root=ROOT):
    # Do not let the common lock file replace a CUDA/CPU wheel with another build.
    index = f'https://download.pytorch.org/whl/{device}'
    return [
        [str(python), '-m', 'pip', 'install', '--upgrade', 'pip', 'wheel', 'setuptools==75.8.0'],
        [str(python), '-m', 'pip', 'install', f'torch=={TORCH_VERSION}+{device}', f'torchaudio=={TORCH_VERSION}+{device}', '--index-url', index],
        [str(python), '-m', 'pip', 'install', '-r', str(root / 'requirements.lock.txt')],
        [str(python), '-m', 'pip', 'check'],
    ]


def run(command, *, env=None, dry_run=False, capture=False):
    # Argument lists are used end to end: a model URL or path is never shell code.
    if not capture:
        print('+ ' + subprocess.list2cmdline(list(map(str, command))), flush=True)
    if dry_run:
        return ''
    result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env, check=True,
                            text=True, encoding='utf-8', errors='replace',
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else ''


def environment():
    env = os.environ.copy()
    env.update(PYTHONUTF8='1', PYTHONUNBUFFERED='1',
               PIP_CACHE_DIR=str(ROOT / '.cache/pip'), HF_HOME=str(ROOT / '.cache/huggingface'),
               HF_HUB_DISABLE_XET='1', HF_HUB_DOWNLOAD_TIMEOUT='120')
    # Isolate this project's venv from another activated Python environment.
    env.pop('PYTHONHOME', None)
    env.pop('PYTHONPATH', None)
    return env


def main(argv=None):
    parser = argparse.ArgumentParser(description='自动配置本地 GPT-SoVITS；模型仅下载到本机。')
    parser.add_argument('--device', choices=['auto', 'cu126', 'cu128', 'cpu'], default='auto')
    parser.add_argument('--model-url', help=f'Hugging Face 模型仓库网址，默认 {DEFAULT_MODEL}')
    parser.add_argument('--revision', help='角色仓库分支或提交；默认预设固定提交，其他仓库默认 main')
    parser.add_argument('--gpt-file', help='仓库内 GPT .ckpt 路径')
    parser.add_argument('--sovits-file', help='仓库内 v2Pro SoVITS .pth 路径')
    parser.add_argument('--reference-file', help='仓库内参考 WAV 路径')
    parser.add_argument('--reference-text', help='参考音频准确转写；默认从中文文件名推断或询问')
    parser.add_argument('--replace-voice', action='store_true', help='备份并替换已有语音配置')
    parser.add_argument('--non-interactive', action='store_true', help='不询问；自定义仓库有多项选择时需显式指定文件')
    parser.add_argument('--skip-assets', action='store_true', help='开发用途：仅构建环境，不下载模型')
    parser.add_argument('--assets-only', action='store_true', help='复用已安装环境，仅重新准备模型和配置')
    parser.add_argument('--dry-run', action='store_true', help='只显示计划，不写文件、不下载、不安装')
    args = parser.parse_args(argv)
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError('需要 Python 3.11。请安装后重新运行；Linux 还需对应的 python3.11-venv。')
    if platform.system() not in {'Windows', 'Linux'} or platform.machine().lower() not in {'amd64', 'x86_64'}:
        raise RuntimeError('本安装流程面向 Windows / Linux x86_64；其他平台尚未支持。')
    if args.skip_assets and args.assets_only:
        parser.error('--skip-assets 与 --assets-only 不能同时使用')
    if args.dry_run:
        sys.dont_write_bytecode = True
    from download_voice import parse_model_url
    model, _ = parse_model_url(args.model_url or DEFAULT_MODEL)
    device = detect_device(args.device)
    print(f'项目目录：{ROOT}\n运行方案：{device}\n角色来源：{model}', flush=True)
    if device == 'cpu' and args.device == 'auto':
        print('没有检测到支持本安装方案的 NVIDIA 驱动，选择 CPU；无需安装系统 CUDA Toolkit。', flush=True)
    env = environment()
    python = venv_python()
    vendor = ROOT / 'vendor/GPT-SoVITS'
    if not args.assets_only:
        if not args.dry_run and not shutil.which('git'):
            raise RuntimeError('未找到 Git，请先安装 Git，然后重新运行。')
        if not vendor.exists():
            run(['git', 'clone', '--no-checkout', '--depth', '1', UPSTREAM, vendor], env=env, dry_run=args.dry_run)
            run(['git', '-C', vendor, 'fetch', '--depth', '1', 'origin', COMMIT], env=env, dry_run=args.dry_run)
            run(['git', '-C', vendor, 'checkout', '--detach', COMMIT], env=env, dry_run=args.dry_run)
        elif not args.dry_run:
            actual = run(['git', '-C', vendor, 'rev-parse', 'HEAD'], env=env, capture=True)
            if actual != COMMIT:
                raise RuntimeError('vendor 中的 GPT-SoVITS 版本不同。请使用新目录安装，原目录将保持不动。')
        if not python.is_file():
            run([sys.executable, '-m', 'venv', ROOT / '.venv'], env=env, dry_run=args.dry_run)
        elif not args.dry_run:
            run([python, '-c', "import sys; assert sys.version_info[:2] == (3,11), 'Existing venv must use Python 3.11'"], env=env)
        for command in dependency_commands(python, device):
            run(command, env=env, dry_run=args.dry_run)
        run([python, '-c', PROBE, 'cpu' if device == 'cpu' else 'cuda'], env=env, dry_run=args.dry_run)
    if not args.skip_assets:
        if args.assets_only and not python.is_file() and not args.dry_run:
            raise RuntimeError('请先运行一次完整 setup，准备 .venv 和依赖。')
        run([python, ROOT / 'prepare_assets.py'], env=env, dry_run=args.dry_run)
        command = [python, ROOT / 'scripts/download_voice.py', '--model-url', args.model_url or DEFAULT_MODEL,
                   '--device', 'cpu' if device == 'cpu' else 'cuda']
        for key in ['revision', 'gpt_file', 'sovits_file', 'reference_file', 'reference_text']:
            value = getattr(args, key)
            if value:
                command.extend(['--' + key.replace('_', '-'), value])
        for key in ['replace_voice', 'non_interactive']:
            if getattr(args, key):
                command.append('--' + key.replace('_', '-'))
        run(command, env=env, dry_run=args.dry_run)
        run([python, ROOT / 'tts.py', '--check'], env=env, dry_run=args.dry_run)
    if args.dry_run:
        print('计划显示完毕；没有写入或下载任何文件。')
    elif args.skip_assets:
        print('环境构建完成。尚未下载模型；运行 setup --assets-only 完成剩余步骤。')
    else:
        print('安装完成！下一步运行 install-plugin.bat（Windows）或 bash install-plugin.sh（Linux）。')
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'\n安装未完成：{error}\n请按 README 排查后重跑同一命令，已下载的内容会尽量复用。', file=sys.stderr)
        raise SystemExit(1)

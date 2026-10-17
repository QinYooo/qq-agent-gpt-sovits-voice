"""Download a v2Pro character from a Hugging Face repository and configure it."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = 'Sucial/seren-azuma-gpt-sovits'
DEFAULT_REVISION = '0763f55fb51e0b4be511c2010abeb1afa896a9a7'
DEFAULT_GPT = 'GPT_weights_v2Pro/azuma-e15.ckpt'
DEFAULT_SOVITS = 'SoVITS_weights_v2Pro/azuma_e8_s2928.pth'


def parse_model_url(value):
    if '://' not in value:
        repo, revision = value.strip().strip('/'), None
    else:
        url = urlparse(value.strip())
        if url.scheme != 'https' or url.hostname != 'huggingface.co' or url.username or url.password or url.query or url.fragment:
            raise ValueError('请填写 https://huggingface.co/作者/仓库 形式的模型页链接，不接受带密钥的网址。')
        parts = url.path.strip('/').split('/')
        if len(parts) < 2 or (len(parts) > 2 and (parts[2] != 'tree' or len(parts) < 4)):
            raise ValueError('需要模型仓库页面链接，而不是单个文件的下载链接。')
        repo = '/'.join(parts[:2])
        revision = unquote('/'.join(parts[3:])) if len(parts) > 2 else None
    if not re.fullmatch(r'[A-Za-z0-9][\w.-]*/[A-Za-z0-9][\w.-]*', repo, flags=re.ASCII):
        raise ValueError('模型仓库应为 作者/仓库名。')
    return repo, revision


def safe_file(name):
    path = PurePosixPath(name)
    if not name or '\\' in name or path.is_absolute() or ':' in name or any(part in {'.', '..'} for part in name.split('/')):
        raise ValueError('仓库内文件路径不合法。')
    return name


def choose_file(files, suffix, label, explicit=None, preferred=None, interactive=True):
    candidates = sorted(f for f in files if f.lower().endswith(suffix))
    if explicit:
        safe_file(explicit)
        if explicit not in candidates:
            raise ValueError(f'{label}文件不在指定仓库或后缀不符：{explicit}')
        return explicit
    if preferred and preferred in candidates:
        return preferred
    pro = [f for f in candidates if 'v2pro' in f.lower() and 'v2proplus' not in f.lower()]
    if pro:
        candidates = pro
    if not candidates:
        raise ValueError(f'仓库内没有 {label} {suffix} 文件，请确认是 GPT-SoVITS v2Pro 模型。')
    if len(candidates) == 1:
        return safe_file(candidates[0])
    if not interactive:
        raise ValueError(f'{label}有多个候选，请使用对应的 --gpt-file / --sovits-file / --reference-file 参数指定。')
    print(f'\n请选择{label}：')
    for index, item in enumerate(candidates, 1):
        print(f'  {index}. {item}')
    while True:
        value = input('输入序号后回车：').strip()
        if value.isdigit() and 1 <= int(value) <= len(candidates):
            return safe_file(candidates[int(value) - 1])
        print('序号无效，请重试。')


def transcription(reference, explicit, interactive):
    if explicit and explicit.strip():
        return explicit.strip()
    stem = PurePosixPath(reference).stem
    # The default model publishes reference transcripts as Chinese WAV names.
    if re.search(r'[\u3400-\u9fff]', stem) and not re.fullmatch(r'(?:参考音频|参考|音频|片段|测试)\d*', stem):
        if not interactive:
            return stem
        value = input(f'参考转写默认取文件名「{stem}」，直接回车确认，或输入准确转写：').strip()
        return value or stem
    if not interactive:
        raise ValueError('无法从参考文件名可靠获得转写，请用 --reference-text 提供准确转写。')
    while True:
        value = input('请输入参考音频的准确逐字转写：').strip()
        if value:
            return value


def write_config(config, root=ROOT, replace=False):
    path = root / 'voice.json'
    if path.exists():
        if not replace:
            raise FileExistsError('已有 voice.json；请使用 --replace-voice 才会备份并替换。')
        backup_dir = root / '.backups'
        backup_dir.mkdir(exist_ok=True)
        shutil.copy2(path, backup_dir / f'voice-{datetime.now():%Y%m%d-%H%M%S-%f}.json')
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def prepare(args, root=ROOT, api=None, download=None, audio_info=None):
    repo, url_revision = parse_model_url(args.model_url)
    configured = root / 'voice.json'
    if configured.exists() and not args.replace_voice:
        print('保留现有 voice.json 与角色资源；更换角色请显式添加 --replace-voice。')
        return
    if api is None:
        from huggingface_hub import HfApi, hf_hub_download
        import soundfile
        api, download, audio_info = HfApi(), hf_hub_download, soundfile.info
    revision = args.revision or url_revision or (DEFAULT_REVISION if repo == DEFAULT_REPO else 'main')
    info = api.model_info(repo, revision=revision)
    resolved_revision = info.sha
    files = [item.rfilename for item in info.siblings]
    default = repo == DEFAULT_REPO and revision == DEFAULT_REVISION
    interactive = not args.non_interactive
    gpt = choose_file(files, '.ckpt', 'GPT 权重', args.gpt_file, DEFAULT_GPT if default else None, interactive)
    sovits = choose_file(files, '.pth', 'SoVITS v2Pro 权重', args.sovits_file, DEFAULT_SOVITS if default else None, interactive)
    # Select the same reference family as the previously verified preset without
    # publishing the entire reference transcription in a source-code constant.
    preferred_reference = next((f for f in sorted(files) if f.endswith('.wav') and '情感电台' in f), None) if default else None
    reference = choose_file(files, '.wav', '参考 WAV', args.reference_file, preferred_reference, interactive)
    text = transcription(reference, args.reference_text, interactive and not default)
    directory = root / 'models' / repo.replace('/', '--')
    directory.mkdir(parents=True, exist_ok=True)
    downloaded = {}
    for key, name in [('gpt_weights', gpt), ('sovits_weights', sovits), ('reference_audio', reference)]:
        safe_file(name)
        print(f'下载 {repo} / {name}', flush=True)
        path = Path(download(repo_id=repo, filename=name, revision=resolved_revision, local_dir=directory))
        if not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError('下载结果位于模型目录以外。')
        downloaded[key] = path
    duration = audio_info(downloaded['reference_audio']).duration
    if not 3 <= duration <= 10:
        raise ValueError(f'参考音频需为 3–10 秒，实际 {duration:.2f} 秒，请用 --reference-file 选择其他文件。')
    config = json.loads((root / 'voice.example.json').read_text(encoding='utf-8-sig'))
    config.update({key: path.relative_to(root).as_posix() for key, path in downloaded.items()})
    config.update(name=repo.rsplit('/', 1)[-1], reference_text=text, device=args.device,
                  reference_language='all_zh', text_language='zh')
    config['source'] = {'url': f'https://huggingface.co/{repo}', 'revision': resolved_revision}
    write_config(config, root, args.replace_voice)
    print(f'已生成 voice.json，参考语音 {duration:.2f} 秒；模型仅保存在本机 models/。')


def main(argv=None):
    parser = argparse.ArgumentParser(description='从 Hugging Face 下载 v2Pro 角色模型并生成本地配置。')
    parser.add_argument('--model-url', default=DEFAULT_REPO)
    parser.add_argument('--revision')
    for flag in ['gpt-file', 'sovits-file', 'reference-file', 'reference-text']:
        parser.add_argument('--' + flag)
    parser.add_argument('--device', choices=['cuda', 'cpu'], default='cuda')
    parser.add_argument('--replace-voice', action='store_true')
    parser.add_argument('--non-interactive', action='store_true')
    args = parser.parse_args(argv)
    prepare(args)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    try:
        main()
    except (ValueError, OSError, RuntimeError) as error:
        print(f'角色配置未完成：{error}', file=sys.stderr)
        raise SystemExit(1)

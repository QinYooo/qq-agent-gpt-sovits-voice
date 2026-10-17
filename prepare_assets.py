"""Download shared upstream inference assets; never download character voices."""
from __future__ import annotations

import os
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / 'vendor' / 'GPT-SoVITS'
os.environ.setdefault('HF_HOME', str(ROOT / '.cache' / 'huggingface'))
os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '120')

SOURCES = [
    {
        'repo': 'lj1995/GPT-SoVITS',
        'revision': '8f8857563c040d542de108a2c18b0425abd6c9c5',
        'directory': VENDOR / 'GPT_SoVITS' / 'pretrained_models',
        'patterns': ['chinese-hubert-base/*', 'chinese-roberta-wwm-ext-large/*',
                     'sv/pretrained_eres2netv2w24s4ep4.ckpt'],
    },
    {
        'repo': 'XXXXRT/GPT-SoVITS-Pretrained',
        'revision': '0c47645e02a7bc3688d7b263b0042c81e3cd82cd',
        'directory': ROOT / 'models' / 'downloads',
        'patterns': ['G2PWModel.zip'],
    },
]


def main() -> None:
    from huggingface_hub import snapshot_download
    import nltk

    if not (VENDOR / 'GPT_SoVITS').is_dir():
        raise SystemExit('Run setup.ps1 to prepare the pinned upstream source first.')
    for source in SOURCES:
        print(f"Downloading shared assets: {source['repo']}", flush=True)
        snapshot_download(source['repo'], revision=source['revision'],
                          local_dir=source['directory'], allow_patterns=source['patterns'],
                          max_workers=3)
    text_dir = VENDOR / 'GPT_SoVITS' / 'text'
    if not (text_dir / 'G2PWModel' / 'g2pW.onnx').is_file():
        with zipfile.ZipFile(ROOT / 'models' / 'downloads' / 'G2PWModel.zip') as archive:
            for item in archive.infolist():
                if not (text_dir / item.filename).resolve().is_relative_to(text_dir.resolve()):
                    raise ValueError('Archive contains a path outside its destination')
            archive.extractall(text_dir)
    for package in ['averaged_perceptron_tagger', 'averaged_perceptron_tagger_eng', 'cmudict']:
        if not nltk.download(package, download_dir=str(ROOT / '.cache' / 'nltk_data'), quiet=True):
            raise RuntimeError(f'NLTK download failed: {package}')
    print('Shared assets ready. Character weights and reference audio must be supplied separately.')


if __name__ == '__main__':
    main()

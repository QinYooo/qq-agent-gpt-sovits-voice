"""Fail closed on unexpected tracked files, media, weights, and common secrets."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {
    '.gitattributes', '.gitignore', '.github/workflows/ci.yml', 'LICENSE',
    'THIRD_PARTY_NOTICES.md', 'PRIVACY.md', 'README.md', 'package.json',
    'voice.example.json', 'setup.bat', 'setup.sh', 'prepare_assets.py', 'tts.py', 'tts_server.py',
    'requirements.txt', 'requirements.lock.txt', 'run_tts.bat',
    'scripts/check_publication.py', 'scripts/setup.py', 'scripts/download_voice.py',
    'scripts/install_plugin.py', 'scripts/python.cmd', 'scripts/python.sh',
    'install-plugin.bat', 'install-plugin.sh', 'run_tts.sh', 'docs/development.md',
    'plugins/azuma-voice/plugin.json', 'plugins/azuma-voice/index.js',
    'plugins/azuma-voice/engine.js', 'plugins/azuma-voice/worker.js',
    'plugins/azuma-voice/README.md', 'tests/voice.test.mjs',
    'tests/worker.test.mjs', 'tests/test_tts_server.py', 'tests/test_installers.py',
    'tests/installation.test.mjs', 'plugins/azuma-voice/installation.js',
}
PATTERNS = {
    'user profile path': re.compile(r'(?i)[a-z]:[\\/]Users[\\/][^\s"\']+'),
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'API token': re.compile(r'\b(?:sk-[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b'),
    'private email': re.compile(r'\b[A-Za-z0-9._%+-]+@(?!users\.noreply\.github\.com\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
    'credential in URL': re.compile(r'https?://[^\s/@:]+:[^\s/@]+@'),
}


def main():
    files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    files = {name for name in files if name}
    if not files:
        raise SystemExit('No tracked files. Stage the intended publication files first.')
    issues = []
    for name in sorted(files):
        if name not in ALLOWED:
            issues.append(f'{name}: outside publication allowlist')
            continue
        path = ROOT / name
        if path.is_symlink() or path.stat().st_size > 1024 * 1024:
            issues.append(f'{name}: symlink or oversized file')
            continue
        try:
            content = path.read_text(encoding='utf-8-sig')
        except UnicodeError:
            issues.append(f'{name}: non-text file')
            continue
        if '\0' in content:
            issues.append(f'{name}: binary content')
        for label, pattern in PATTERNS.items():
            if pattern.search(content):
                issues.append(f'{name}: possible {label}')
    for name in sorted(ALLOWED - files):
        issues.append(f'{name}: missing expected source file')
    if issues:
        print('\n'.join(issues), file=sys.stderr)
        raise SystemExit(1)
    print(f'Publication checks passed: {len(files)} allowlisted text files; no weights, media or detected secrets.')


if __name__ == '__main__':
    main()

param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONUTF8 = '1'
$env:PIP_CACHE_DIR = Join-Path $PSScriptRoot '.cache\pip'
$env:HF_HOME = Join-Path $PSScriptRoot '.cache\huggingface'
$env:HF_HUB_DISABLE_XET = '1'
$env:HF_HUB_DOWNLOAD_TIMEOUT = '120'
$upstreamCommit = '1b47ca07ef43a284e0b8bd7f29d3e1e3ff76082a'
$repo = Join-Path $PSScriptRoot 'vendor\GPT-SoVITS'
& $Python -c "import sys; assert sys.version_info[:2] == (3, 11), 'Python 3.11 is required'"
if ($LASTEXITCODE -ne 0) { throw 'Choose Python 3.11 with -Python <path-to-python.exe>.' }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Install Git first.' }
if (-not (Test-Path -LiteralPath $repo)) {
    git clone --no-checkout --depth 1 https://github.com/RVC-Boss/GPT-SoVITS.git $repo
    if ($LASTEXITCODE -ne 0) { throw 'Upstream source download failed.' }
    git -C $repo fetch --depth 1 origin $upstreamCommit
    if ($LASTEXITCODE -ne 0) { throw 'Cannot fetch pinned upstream commit.' }
    git -C $repo checkout --detach $upstreamCommit
    if ($LASTEXITCODE -ne 0) { throw 'Cannot check out pinned upstream commit.' }
}
$actualCommit = git -C $repo rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $actualCommit -ne $upstreamCommit) { throw 'Unexpected upstream revision; preserve your existing folder and use a fresh checkout.' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create Python environment.' }
}
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $venvPython -c "import sys; assert sys.version_info[:2] == (3, 11)"
if ($LASTEXITCODE -ne 0) { throw 'Existing .venv must use Python 3.11.' }
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip setup failed.' }
& $venvPython -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu126
if ($LASTEXITCODE -ne 0) { throw 'CUDA PyTorch installation failed.' }
& $venvPython -m pip install -r requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Inference dependency installation failed.' }
& $venvPython prepare_assets.py
if ($LASTEXITCODE -ne 0) { throw 'Shared inference asset download failed.' }
if (-not (Test-Path -LiteralPath 'voice.json')) {
    Copy-Item -LiteralPath 'voice.example.json' -Destination 'voice.json'
}
Write-Host 'Dependencies ready. Follow README to supply character weights and a reference WAV, edit voice.json, then run tts.py --check.'

param(
    [string]$AgentPath = (Join-Path $env:LOCALAPPDATA 'Programs\QQ Agent\resources\app'),
    [string]$TtsDir = (Split-Path -Parent $PSScriptRoot)
)
$ErrorActionPreference = 'Stop'
$agent = (Resolve-Path -LiteralPath $AgentPath).Path
$ttsProject = (Resolve-Path -LiteralPath $TtsDir).Path
if (-not (Test-Path -LiteralPath (Join-Path $agent 'src\sender.js'))) { throw 'AgentPath must be the QQ Agent app folder containing src/sender.js and plugins/.' }
if (-not (Test-Path -LiteralPath (Join-Path $ttsProject 'tts_server.py'))) { throw 'TtsDir must contain tts_server.py.' }
$target = [IO.Path]::GetFullPath((Join-Path $agent 'plugins\azuma-voice'))
$pluginsRoot = [IO.Path]::GetFullPath((Join-Path $agent 'plugins'))
if (-not $target.StartsWith($pluginsRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid plugin destination.' }
if (Test-Path -LiteralPath $target) { throw 'azuma-voice already exists. Back up the existing plugin before replacing it; this installer will not overwrite it.' }
New-Item -ItemType Directory -Path $target -Force | Out-Null
$source = Join-Path (Split-Path -Parent $PSScriptRoot) 'plugins\azuma-voice'
foreach ($name in @('plugin.json', 'index.js', 'engine.js', 'worker.js', 'README.md')) {
    Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $target $name)
}
$manifestPath = Join-Path $target 'plugin.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$manifest.settings.sovitsDir = $ttsProject
$manifest.configSchema.sovitsDir.default = $ttsProject
$json = $manifest | ConvertTo-Json -Depth 20
[IO.File]::WriteAllText($manifestPath, $json, [Text.UTF8Encoding]::new($false))
Write-Host "Installed azuma-voice in $target"
Write-Host 'In QQ Agent, trust only this plugin if prompted. Confirm its project directory in plugin settings. Existing stored settings take precedence over manifest defaults.'

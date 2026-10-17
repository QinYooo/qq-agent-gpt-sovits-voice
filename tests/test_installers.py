import argparse
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import download_voice
import install_plugin
spec = importlib.util.spec_from_file_location('voice_setup', ROOT / 'scripts/setup.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class DeviceTests(unittest.TestCase):
    def test_auto_device_selection_uses_driver_and_gpu_architecture(self):
        self.assertEqual(bootstrap.choose_device('auto'), 'cpu')
        self.assertEqual(bootstrap.choose_device('auto', 'CUDA Version: 12.5', '8.9'), 'cpu')
        self.assertEqual(bootstrap.choose_device('auto', 'CUDA Version: 13.2 RTX 4070', '8.9'), 'cu126')
        self.assertEqual(bootstrap.choose_device('auto', 'CUDA Version: 12.8 RTX 5090', '12.0'), 'cu128')
        with self.assertRaisesRegex(RuntimeError, 'cu128'):
            bootstrap.choose_device('auto', 'CUDA Version: 12.6 RTX 5090', '12.0')
        self.assertEqual(bootstrap.choose_device('cpu', 'CUDA Version: 13.2', '12.0'), 'cpu')

    def test_torch_build_switch_is_explicit_and_common_lock_does_not_override_it(self):
        for device in ['cpu', 'cu126', 'cu128']:
            commands = bootstrap.dependency_commands(Path('python'), device)
            self.assertIn(f'torch==2.8.0+{device}', commands[1])
            self.assertTrue(commands[1][-1].endswith('/' + device))
        lock = (ROOT / 'requirements.lock.txt').read_text()
        self.assertNotIn('\ntorch==', lock)
        self.assertNotIn('\ntorchaudio==', lock)
        self.assertIn('sys_platform == "win32"', lock)

    def test_dry_run_from_another_directory_is_anchored_to_script_and_does_not_create_venv(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, ROOT / 'scripts/setup.py', '--dry-run', '--device', 'cpu', '--non-interactive'],
                                    cwd=tmp, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(str(ROOT), result.stdout)
            self.assertIn('torch==2.8.0+cpu', result.stdout)
            self.assertFalse((Path(tmp) / '.venv').exists())


class DownloadTests(unittest.TestCase):
    def args(self, **patch):
        values = dict(model_url=download_voice.DEFAULT_REPO, revision=None, gpt_file=None,
                      sovits_file=None, reference_file=None, reference_text=None,
                      device='cpu', replace_voice=False, non_interactive=True)
        values.update(patch)
        return argparse.Namespace(**values)

    def test_repository_urls_and_paths_are_validated(self):
        self.assertEqual(download_voice.parse_model_url('https://huggingface.co/owner/voice/tree/dev'), ('owner/voice', 'dev'))
        for bad in ['http://huggingface.co/a/b', 'https://example.org/a/b',
                    'https://huggingface.co/a/b?token=fixture', 'https://huggingface.co/a/b/resolve/main/a.ckpt']:
            with self.assertRaises(ValueError):
                download_voice.parse_model_url(bad)
        for bad in ['../escape.ckpt', '/escape.ckpt', 'x/../../escape', 'x\\escape', 'disk:file']:
            with self.assertRaises(ValueError):
                download_voice.safe_file(bad)

    def test_multiple_custom_weights_require_selection_in_unattended_mode(self):
        with self.assertRaisesRegex(ValueError, '多个候选'):
            download_voice.choose_file(['a.ckpt', 'b.ckpt'], '.ckpt', 'GPT', interactive=False)
        self.assertEqual(download_voice.choose_file(['a.ckpt', 'b.ckpt'], '.ckpt', 'GPT', explicit='b.ckpt'), 'b.ckpt')

    def test_default_model_generates_relative_paths_and_exact_transcript_after_audio_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copyfile(ROOT / 'voice.example.json', root / 'voice.example.json')
            names = [download_voice.DEFAULT_GPT, download_voice.DEFAULT_SOVITS, 'Reference_Audios/情感电台示例.wav']
            info = SimpleNamespace(sha='fixed-revision', siblings=[SimpleNamespace(rfilename=n) for n in names])
            calls = []
            def download(**kwargs):
                calls.append(kwargs)
                path = kwargs['local_dir'] / kwargs['filename']
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'fixture')
                return str(path)
            api = SimpleNamespace(model_info=lambda *a, **kw: info)
            with redirect_stdout(io.StringIO()):
                download_voice.prepare(self.args(), root, api, download, lambda path: SimpleNamespace(duration=6.44))
            config = json.loads((root / 'voice.json').read_text(encoding='utf-8'))
            self.assertEqual(config['device'], 'cpu')
            self.assertEqual(config['reference_text'], '情感电台示例')
            self.assertFalse(Path(config['gpt_weights']).is_absolute())
            self.assertEqual({c['revision'] for c in calls}, {'fixed-revision'})
            before = (root / 'voice.json').read_bytes()
            with redirect_stdout(io.StringIO()):
                download_voice.prepare(self.args(), root, api=SimpleNamespace())
            self.assertEqual((root / 'voice.json').read_bytes(), before)

    def test_config_replacement_requires_opt_in_and_keeps_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'voice.json').write_text('{"existing":true}')
            with self.assertRaises(FileExistsError):
                download_voice.write_config({'new': True}, root)
            download_voice.write_config({'new': True}, root, replace=True)
            backup = list((root / '.backups').glob('*.json'))
            self.assertEqual(len(backup), 1)
            self.assertEqual(json.loads(backup[0].read_text()), {'existing': True})


class PluginInstallerTests(unittest.TestCase):
    def fixture(self, root):
        app = root / 'QQ Agent/resources/app'
        (app / 'src').mkdir(parents=True)
        (app / 'src/sender.js').write_text('// fixture')
        (app / 'src/config.js').write_text('// fixture')
        tts = root / 'Voice Project'
        python = bootstrap.venv_python(tts)
        python.parent.mkdir(parents=True)
        python.write_text('fixture')
        (tts / 'voice.json').write_text('{}')
        (tts / 'tts_server.py').write_text('# fixture')
        return app, tts

    def test_installer_uses_tts_project_directory_and_leaves_host_config_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app, tts = self.fixture(root)
            (app / 'data').mkdir()
            config = app / 'data/config.json'
            original = '{"api":{"apiKey":"fixture-value"},"trustedPlugins":[]}'
            config.write_text(original)
            self.assertEqual(install_plugin.find_app(root / 'QQ Agent'), app.resolve())
            target, backup = install_plugin.install(app, tts)
            self.assertIsNone(backup)
            manifest = json.loads((target / 'plugin.json').read_text(encoding='utf-8'))
            deployment = json.loads((target / 'installation.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['settings']['sovitsDir'], str(tts.resolve()))
            self.assertEqual(deployment['projectDir'], str(tts.resolve()))
            self.assertEqual(config.read_text(), original)
            self.assertEqual(set(p.name for p in target.iterdir()), set(install_plugin.PLUGIN_FILES) | {'installation.json'})

    def test_upgrade_requires_opt_in_and_preserves_old_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            app, tts = self.fixture(Path(tmp))
            target, _ = install_plugin.install(app, tts)
            old = (target / 'installation.json').read_bytes()
            with self.assertRaises(FileExistsError):
                install_plugin.install(app, tts)
            _, backup = install_plugin.install(app, tts, upgrade=True)
            self.assertEqual((backup / 'installation.json').read_bytes(), old)
            self.assertNotEqual((target / 'installation.json').read_bytes(), old)


if __name__ == '__main__':
    unittest.main()

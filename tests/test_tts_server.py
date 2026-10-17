import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tts
import tts_server


class FakeVoice:
    def __init__(self):
        self.calls = []
        self.fail = False

    def synthesize(self, text, output):
        self.calls.append(text)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b'RIFF' + b'\0' * 4 + b'WAVE' + b'\0' * 36)
        output.with_suffix('.json').write_text('{}')
        if self.fail:
            raise RuntimeError('test synthesis failure')


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.old_root = tts_server.ROOT
        tts_server.ROOT = Path(cls.temp.name)
        cls.voice = FakeVoice()
        cls.server = tts_server.create_server(cls.voice, 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        cls.server.server_close()
        tts_server.ROOT = cls.old_root
        cls.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        result = response.status, response.getheader('Content-Type'), response.read()
        conn.close()
        return result

    def test_health_and_loopback_binding(self):
        self.assertEqual(self.server.server_address[0], '127.0.0.1')
        status, _, body = self.request('GET', '/health')
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)['ready'])
        self.assertEqual(self.request('GET', '/unknown')[0], 404)

    def test_valid_request_returns_wav_and_removes_local_artifacts(self):
        status, content_type, body = self.request('POST', '/tts',
            json.dumps({'text': '你好'}), {'Content-Type': 'application/json'})
        self.assertEqual(status, 200)
        self.assertEqual(content_type, 'audio/wav')
        self.assertEqual(body[:4], b'RIFF')
        self.assertEqual(self.voice.calls[-1], '你好')
        self.assertEqual(list(Path(self.temp.name).rglob('*.wav')), [])
        self.assertEqual(list(Path(self.temp.name).rglob('*.json')), [])

    def test_browser_and_unexpected_host_requests_are_rejected_before_synthesis(self):
        before = len(self.voice.calls)
        for headers in [
            {'Content-Type': 'application/json', 'Origin': 'https://example.org'},
            {'Content-Type': 'application/json', 'Origin': ''},
            {'Content-Type': 'application/json', 'Host': 'example.org'},
            {'Content-Type': 'text/plain'},
        ]:
            self.assertEqual(self.request('POST', '/tts', '{"text":"hello"}', headers)[0], 403)
        self.assertEqual(len(self.voice.calls), before)

    def test_invalid_payloads_do_not_invoke_synthesis(self):
        before = len(self.voice.calls)
        for payload in ['{}', '[]', 'null', '{bad', '{"text":42}', json.dumps({'text': '字' * 601})]:
            self.assertEqual(self.request('POST', '/tts', payload, {'Content-Type': 'application/json'})[0], 400)
        self.assertEqual(len(self.voice.calls), before)

    def test_failure_is_reported_without_leaking_exception_and_cleans_up(self):
        self.voice.fail = True
        try:
            status, _, body = self.request('POST', '/tts', '{"text":"hello"}',
                                          {'Content-Type': 'application/json'})
            self.assertEqual(status, 500)
            self.assertNotIn(b'test synthesis failure', body)
            self.assertEqual(list(Path(self.temp.name).rglob('*.wav')), [])
            self.assertEqual(list(Path(self.temp.name).rglob('*.json')), [])
        finally:
            self.voice.fail = False


class ConfigurationTests(unittest.TestCase):
    def test_missing_private_config_explains_local_setup(self):
        with self.assertRaisesRegex(FileNotFoundError, 'voice.example.json'):
            tts.load_config(Path('missing-private-config.json'))

    def test_placeholder_cannot_be_used_as_real_reference_transcription(self):
        with self.assertRaisesRegex(ValueError, '占位'):
            tts.load_config(ROOT / 'voice.example.json')


if __name__ == '__main__':
    unittest.main()

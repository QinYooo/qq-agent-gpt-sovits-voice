"""Loopback-only TTS bridge used by the QQbot. Models remain loaded."""
from __future__ import annotations

import argparse
import faulthandler
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from uuid import uuid4

from tts import ROOT, VoiceSynthesizer


def create_server(voice, port: int = 9881) -> HTTPServer:
    """Accept an already loaded synthesizer; also permits GPU-free HTTP tests."""
    class Handler(BaseHTTPRequestHandler):
        timeout = 30

        def allowed_host(self) -> bool:
            return self.headers.get('Host', '') in {
                f'127.0.0.1:{self.server.server_port}',
                f'localhost:{self.server.server_port}',
            }

        def respond(self, code: int, payload: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            if not self.allowed_host():
                self.send_error(403)
                return
            if self.path != "/health":
                self.send_error(404)
                return
            self.respond(200, b'{"ready":true,"voice":"azuma-v2Pro"}', "application/json")

        def do_POST(self) -> None:
            if self.path != "/tts":
                self.send_error(404)
                return
            # Reject browser form requests; this endpoint is for the local bot only.
            if not self.allowed_host() or 'Origin' in self.headers or self.headers.get_content_type() != "application/json":
                self.send_error(403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    raise ValueError("请求大小超限")
                data = json.loads(self.rfile.read(length))
                text = data.get("text")
                if not isinstance(text, str) or not text.strip() or len(text) > 600:
                    raise ValueError("文字需为 1–600 个字符")
            except (ValueError, TypeError, AttributeError):
                self.respond(400, b'{"error":"invalid text request"}', "application/json")
                return
            output = ROOT / "outputs" / "qqbot" / f"{uuid4().hex}.wav"
            code, content_type = 200, 'audio/wav'
            try:
                voice.synthesize(text, output)
                if output.stat().st_size > 20 * 1024 * 1024:
                    raise ValueError('Generated WAV exceeds 20 MiB')
                payload = output.read_bytes()
            except Exception:
                code, content_type = 500, 'application/json'
                payload = b'{"error":"speech synthesis failed; see runtime/tts.log"}'
            finally:
                output.unlink(missing_ok=True)
                output.with_suffix(".json").unlink(missing_ok=True)
            # Complete cleanup before the client receives its response. This also
            # avoids races between a fast client and deletion on another thread.
            self.respond(code, payload, content_type)

        def log_message(self, format: str, *args: object) -> None:
            print(f"TTS HTTP: {format % args}", flush=True)

    return HTTPServer(("127.0.0.1", port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="QQ Agent 本地 GPT-SoVITS 语音服务")
    parser.add_argument("--port", type=int, default=9881)
    parser.add_argument("--config", default=str(ROOT / 'voice.json'))
    parser.add_argument("--device", choices=['auto', 'cuda', 'cpu'], default='auto')
    args = parser.parse_args()
    # Surface the actual blocked import if a machine takes unusually long to load.
    faulthandler.dump_traceback_later(30, repeat=True)
    try:
        from tts import project_path
        voice = VoiceSynthesizer(project_path(args.config), args.device)
    finally:
        faulthandler.cancel_dump_traceback_later()
    server = create_server(voice, args.port)
    print(f"TTS ready: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

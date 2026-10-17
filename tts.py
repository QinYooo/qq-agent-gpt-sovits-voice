"""Small local GPT-SoVITS v2Pro text-to-WAV demo, with a reusable Python class."""
from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parent


@contextmanager
def backend_log():
    directory = ROOT / "runtime"
    directory.mkdir(exist_ok=True)
    with (directory / "tts.log").open("a", encoding="utf-8") as log:
        with redirect_stdout(log), redirect_stderr(log):
            try:
                yield
            except Exception:
                traceback.print_exc(file=log)
                raise


def project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve()


def load_config(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError("请先把 voice.example.json 复制为 voice.json，并按 README 配置自己的模型与参考语音。")
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    required_keys = ["repo_dir", "gpt_weights", "sovits_weights", "reference_audio",
                     "reference_text", "reference_language", "text_language", "speed", "seed",
                     "top_k", "top_p", "temperature", "repetition_penalty"]
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValueError("语音配置缺少字段：" + ", ".join(missing_keys))
    if not isinstance(config['reference_text'], str) or not config['reference_text'].strip():
        raise ValueError("voice.json 中 reference_text 不能为空。")
    if config['reference_text'] == '请替换为参考音频的准确逐字转写':
        raise ValueError("请先将 reference_text 的占位文字替换为参考音频的准确转写。")
    repo = project_path(config["repo_dir"])
    required = [
        repo / "GPT_SoVITS" / "TTS_infer_pack" / "TTS.py",
        *(project_path(config[key]) for key in ["gpt_weights", "sovits_weights", "reference_audio"]),
        repo / "GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large/pytorch_model.bin",
        repo / "GPT_SoVITS/pretrained_models/chinese-hubert-base/pytorch_model.bin",
        repo / "GPT_SoVITS/pretrained_models/sv/pretrained_eres2netv2w24s4ep4.ckpt",
        repo / "GPT_SoVITS/text/G2PWModel/g2pW.onnx",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("缺少资源，请按 README 完成依赖下载、角色权重和参考音频配置：\n" + "\n".join(missing))
    return config


def configure_runtime(repo: Path) -> None:
    # Upstream has relative asset paths; keep all generated caches in this workspace.
    for key, value in {
        "HF_HOME": str(ROOT / ".cache/huggingface"),
        "NLTK_DATA": str(ROOT / ".cache/nltk_data"),
        "NUMBA_CACHE_DIR": str(ROOT / ".cache/numba"),
        "MPLCONFIGDIR": str(ROOT / ".cache/matplotlib"), "MPLBACKEND": "Agg",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "language": "zh_CN", "version": "v2Pro",
        "CUDAGraph": "0",
    }.items():
        os.environ[key] = value
    os.chdir(repo)
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / "GPT_SoVITS"))
    # Use the packaged FFmpeg executable rather than requiring a global install.
    import imageio_ffmpeg
    from tools import portable_runtime
    portable_runtime.FFMPEG_EXE = Path(imageio_ffmpeg.get_ffmpeg_exe())


class VoiceSynthesizer:
    """Load once; call synthesize(text, output) repeatedly from a chatbot."""

    def __init__(self, config_path: Path = ROOT / "voice.json", device: str = "cuda"):
        print("正在加载语音模型，请稍候……", flush=True)
        started = time.perf_counter()
        with backend_log():
            self._load_model(config_path, device)
        print(f"模型已就绪，加载耗时 {time.perf_counter() - started:.1f} 秒。", flush=True)

    def _load_model(self, config_path: Path, device: str):
        self.config = load_config(config_path)
        configure_runtime(project_path(self.config["repo_dir"]))
        import torch
        from TTS_infer_pack.TTS import TTS, TTS_Config
        import fast_langdetect

        # The upstream splitter may otherwise fetch a large classifier on first use.
        # Use the classifier shipped with the installed package for offline inference.
        language_model = Path(fast_langdetect.__file__).parent / "resources" / "lid.176.ftz"
        fast_langdetect.infer._default_detector = fast_langdetect.infer.LangDetector(
            fast_langdetect.infer.LangDetectConfig(custom_model_path=str(language_model))
        )

        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("未检测到可用 CUDA。请运行 setup.ps1，或使用 --device cpu。")
        self.device = device
        torch.set_num_threads(min(8, os.cpu_count() or 1))
        repo = project_path(self.config["repo_dir"])
        pretrained = repo / "GPT_SoVITS" / "pretrained_models"
        settings = TTS_Config({"custom": {
            "version": "v2Pro", "device": device, "is_half": device == "cuda",
            "t2s_weights_path": str(project_path(self.config["gpt_weights"])),
            "vits_weights_path": str(project_path(self.config["sovits_weights"])),
            "bert_base_path": str(pretrained / "chinese-roberta-wwm-ext-large"),
            "cnhuhbert_base_path": str(pretrained / "chinese-hubert-base"),
        }})
        runtime = ROOT / "runtime"
        runtime.mkdir(exist_ok=True)
        settings.configs_path = str(runtime / "tts_infer.yaml")
        self.pipeline = TTS(settings)
        if self.pipeline.configs.version != "v2Pro":
            raise RuntimeError(f"权重实际版本不是 v2Pro: {self.pipeline.configs.version}")

    def synthesize(self, text: str, output: Path, *, speed: float | None = None) -> dict:
        import numpy as np
        import soundfile as sf
        import torch

        text = text.strip()
        if not text or not any(char.isalnum() for char in text):
            raise ValueError("请输入包含汉字、字母或数字的文字。")
        speed = float(self.config["speed"] if speed is None else speed)
        if not 0.5 <= speed <= 2.0:
            raise ValueError("语速范围为 0.5–2.0。")
        output = project_path(str(output))
        if output.suffix.lower() != ".wav":
            raise ValueError("输出文件必须使用 .wav 后缀。")
        request = {
            "text": text, "text_lang": self.config["text_language"],
            "ref_audio_path": str(project_path(self.config["reference_audio"])),
            "prompt_text": self.config["reference_text"],
            "prompt_lang": self.config["reference_language"],
            "text_split_method": "cut5", "batch_size": 1,
            "parallel_infer": False, "split_bucket": False,
            "streaming_mode": False, "return_fragment": False,
            "use_cuda_graph": False, "use_flash_attention": False,
            "speed_factor": speed, "seed": self.config["seed"],
            **{key: self.config[key] for key in ["top_k", "top_p", "temperature", "repetition_penalty"]},
        }
        if self.device == "cuda":
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        chunks, sample_rate = [], None
        with backend_log(), torch.inference_mode():
            for rate, audio in self.pipeline.run(request):
                if sample_rate is not None and rate != sample_rate:
                    raise RuntimeError("音频片段采样率不一致。")
                sample_rate = rate
                chunks.append(audio)
        if self.device == "cuda":
            torch.cuda.synchronize()
        elapsed = time.perf_counter() - started
        if not chunks:
            raise RuntimeError("模型没有返回音频。")
        audio = np.concatenate(chunks)
        if audio.size == 0 or not np.isfinite(audio).all() or np.max(np.abs(audio.astype(float))) == 0:
            raise RuntimeError("模型返回了空白或无效音频。")
        output.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output), audio, sample_rate, subtype="PCM_16")
        duration = len(audio) / sample_rate
        metadata = {
            "text": text, "output": str(output), "sample_rate": sample_rate,
            "duration_seconds": round(duration, 3), "synthesis_seconds": round(elapsed, 3),
            "rtf": round(elapsed / duration, 3), "device": self.device,
            "peak_allocated_vram_mib": round(torch.cuda.max_memory_allocated() / 1024**2) if self.device == "cuda" else 0,
            "gpt_weights": self.config["gpt_weights"], "sovits_weights": self.config["sovits_weights"],
            "reference_audio": self.config["reference_audio"],
            "reference_text": self.config["reference_text"], "seed": self.config["seed"],
            "speed": speed,
        }
        output.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已保存: {output}\n音频 {duration:.2f} 秒；合成 {elapsed:.2f} 秒；RTF {elapsed / duration:.2f}", flush=True)
        return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="GPT-SoVITS v2Pro：输入文字，生成本地 WAV 语音。")
    parser.add_argument("--text", help="直接合成这段文字；省略则进入连续输入模式")
    parser.add_argument("--output", help="WAV 文件路径；交互模式下自动生成文件名")
    parser.add_argument("--config", default=str(ROOT / "voice.json"))
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    parser.add_argument("--speed", type=float)
    parser.add_argument("--play", action="store_true", help="生成后播放（Windows）")
    parser.add_argument("--check", action="store_true", help="检查资源和 CUDA，不加载模型")
    args = parser.parse_args()
    if args.output and args.text is None:
        parser.error("--output 需与 --text 同时使用。")
    try:
        config_path = project_path(args.config)
        if args.check:
            load_config(config_path)
            import torch
            print(f"资源完整；PyTorch {torch.__version__}；CUDA 可用: {torch.cuda.is_available()}")
            if args.device == "cuda" and not torch.cuda.is_available():
                raise RuntimeError("CUDA 不可用。")
            return 0
        synth = VoiceSynthesizer(config_path, args.device)
        print("输入文字后按回车；输入 /quit 退出。", flush=True)
        while True:
            text = args.text if args.text is not None else input("\n文字> ")
            if args.text is None and text.strip().lower() in {"/quit", "/exit"}:
                break
            if args.text is None and not text.strip():
                continue
            output = project_path(args.output) if args.output else ROOT / "outputs" / f"speech_{datetime.now():%Y%m%d_%H%M%S_%f}.wav"
            try:
                synth.synthesize(text, output, speed=args.speed)
                if args.play:
                    import winsound
                    winsound.PlaySound(str(output), winsound.SND_FILENAME)
            except Exception as exc:
                print(f"生成失败: {exc}\n详细日志: {ROOT / 'runtime/tts.log'}", file=sys.stderr, flush=True)
                if args.text is not None:
                    return 1
            if args.text is not None:
                break
        return 0
    except (KeyboardInterrupt, EOFError):
        return 0
    except Exception as exc:
        print(f"启动失败: {exc}\n详细日志: {ROOT / 'runtime/tts.log'}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

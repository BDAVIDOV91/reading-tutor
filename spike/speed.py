"""Speed spike: load ONE local STT model, transcribe one WAV, print one JSON line of timings and memory.

Throwaway measurement script (plan Q4: exempt from TDD, never imported by the app).
The transcript is written to spike/out/<engine>.txt and is never printed.

Usage (from the repo root):
    uv run --project spike python spike/speed.py --engine whisper-small --audio spike/audio/slow.wav
    uv run --project spike python spike/speed.py --engine whisper-small --download   # fetch weights once
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
from pathlib import Path

ENGINES: dict[str, dict] = {
    "whisper-small": {"kind": "whisper", "model": "Systran/faster-whisper-small"},
    "whisper-medium": {"kind": "whisper", "model": "Systran/faster-whisper-medium"},
    "whisper-turbo": {"kind": "whisper", "model": "deepdml/faster-whisper-large-v3-turbo-ct2"},
    "ctc-bg": {"kind": "ctc", "model": "anuragshas/wav2vec2-large-xls-r-300m-bg"},
    "parakeet-v3": {"kind": "parakeet", "model": "nemo-parakeet-tdt-0.6b-v3"},
}

WHISPER_SETTINGS = {
    "language": "bg",
    "condition_on_previous_text": False,
    "vad_filter": True,
    "vad_parameters": {"min_silence_duration_ms": 1000},
}
CTC_CHUNK_S = 15
CTC_STRIDE_S = (4, 2)

OUT_DIR = Path(__file__).resolve().parent / "out"


def rss_anon_mb() -> float | None:
    """Anonymous resident memory; excludes mmap'd weight files, which inflate plain RSS."""
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("RssAnon:"):
                return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        return None
    return None


def peak_rss_mb() -> float:
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)  # Linux: KiB


def load(engine: str):
    spec = ENGINES[engine]
    kind, model_id = spec["kind"], spec["model"]
    if kind == "whisper":
        from faster_whisper import WhisperModel

        return WhisperModel(model_id, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
    if kind == "ctc":
        import torch
        from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor, pipeline

        torch.set_num_threads(os.cpu_count() or 4)
        # Plain processor, not ...WithLM: no n-gram language model (it pulls output toward real words).
        processor = Wav2Vec2Processor.from_pretrained(model_id)
        model = Wav2Vec2ForCTC.from_pretrained(model_id)
        return pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            device="cpu",
        )
    if kind == "parakeet":
        import onnx_asr

        model = onnx_asr.load_model(model_id, quantization="int8")
        # Single clips are limited to roughly 20 to 30 s, so segment with Silero VAD.
        return model.with_vad(onnx_asr.load_vad("silero"))
    raise ValueError(kind)


def transcribe(engine: str, model, audio: Path) -> str:
    kind = ENGINES[engine]["kind"]
    if kind == "whisper":
        import soundfile as sf

        # Decode with soundfile: faster-whisper 1.2.1's PyAV path breaks on current av ("metadata_errors").
        data, sr = sf.read(str(audio), dtype="float32")
        if sr != 16000:
            raise SystemExit(f"expected 16 kHz audio, got {sr}")
        segments, _info = model.transcribe(data, **WHISPER_SETTINGS)
        return " ".join(s.text.strip() for s in segments)  # the generator does the work
    if kind == "ctc":
        import soundfile as sf

        data, sr = sf.read(str(audio), dtype="float32")
        if sr != 16000:
            raise SystemExit(f"expected 16 kHz audio, got {sr}")
        out = model({"raw": data, "sampling_rate": sr}, chunk_length_s=CTC_CHUNK_S, stride_length_s=CTC_STRIDE_S)
        return out["text"]
    if kind == "parakeet":
        return " ".join(seg.text.strip() for seg in model.recognize(str(audio)))
    raise ValueError(kind)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--engine", required=True, choices=sorted(ENGINES))
    p.add_argument("--audio", type=Path)
    p.add_argument("--download", action="store_true", help="fetch weights (online) and exit")
    args = p.parse_args()

    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    if args.download:
        load(args.engine)
        print(json.dumps({"engine": args.engine, "downloaded": True}))
        return 0
    if args.audio is None:
        p.error("--audio is required unless --download")
    repo = Path(__file__).resolve().parent.parent
    audio_abs = args.audio.resolve()
    if any(audio_abs.is_relative_to(repo / d) for d in ("recordings", "data")):
        p.error("refusing audio under recordings/ or data/: the spike takes adult recordings only")
    os.environ["HF_HUB_OFFLINE"] = "1"  # measured runs never touch the network

    import soundfile as sf

    duration_s = sf.info(str(args.audio)).duration

    t0 = time.perf_counter()
    model = load(args.engine)
    load_s = time.perf_counter() - t0
    rss_anon_after_load = rss_anon_mb()

    t1 = time.perf_counter()
    text = transcribe(args.engine, model, args.audio)
    transcribe_s = time.perf_counter() - t1

    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / f"{args.engine}.txt").write_text(text + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "engine": args.engine,
                "model": ENGINES[args.engine]["model"],
                "compute_type": "int8" if ENGINES[args.engine]["kind"] != "ctc" else "float32",
                "audio_s": round(duration_s, 1),
                "load_s": round(load_s, 1),
                "transcribe_s": round(transcribe_s, 1),
                "rtf": round(transcribe_s / duration_s, 2),
                "peak_rss_mb": peak_rss_mb(),
                "rss_anon_after_load_mb": rss_anon_after_load,
                "rss_anon_after_transcribe_mb": rss_anon_mb(),
                "transcript_words": len(text.split()),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

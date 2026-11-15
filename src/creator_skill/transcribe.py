"""Local speech-to-text: mlx-whisper on Apple Silicon when installed, else faster-whisper."""

import importlib.util
import os
import platform
import threading
from functools import cache
from pathlib import Path

DEFAULT_MODEL = os.environ.get("WHISPER_MODEL", "small")
MLX_REPOS = {"large": "mlx-community/whisper-large-v3-mlx"}
_lock = threading.Lock()  # Whisper is compute-bound and mlx shares one GPU: one job at a time


def backend() -> str:
    """Name of the Whisper backend that will be used."""
    apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"
    if apple_silicon and importlib.util.find_spec("mlx_whisper"):
        return "mlx-whisper"
    return "faster-whisper"


@cache
def _faster_model(model: str):  # returns faster_whisper.WhisperModel (imported lazily)
    from faster_whisper import WhisperModel

    return WhisperModel(model, compute_type="int8")


def transcribe(audio: Path, model: str = DEFAULT_MODEL) -> tuple[str, str | None]:
    """Return (text, detected language) for an audio or video file."""
    with _lock:
        return _transcribe(audio, model)


def _transcribe(audio: Path, model: str) -> tuple[str, str | None]:
    if backend() == "mlx-whisper":
        import mlx_whisper

        repo = MLX_REPOS.get(model, f"mlx-community/whisper-{model}-mlx")
        result = mlx_whisper.transcribe(str(audio), path_or_hf_repo=repo)
        return result["text"].strip(), result.get("language")
    # vad_filter skips music-only stretches, where Whisper otherwise invents words
    segments, info = _faster_model(model).transcribe(str(audio), vad_filter=True)
    return " ".join(s.text.strip() for s in segments).strip(), info.language

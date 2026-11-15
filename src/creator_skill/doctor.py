"""Environment check: report what's missing and print the exact command to fix it."""

import importlib.util
import platform
import shutil
import sys
from datetime import date
from pathlib import Path

from yt_dlp.version import __version__ as YT_DLP_VERSION

from . import transcribe

YT_DLP_MAX_AGE_DAYS = 45  # YouTube/TikTok break old yt-dlp releases within weeks
TOOL_SPEC = "creator-skill[mac] @ git+https://github.com/oliverdjohnston/skillify"
IN_UV_TOOL = (Path(sys.prefix) / "uv-receipt.toml").exists()  # installed with `uv tool install`


def _install(args: str) -> str:
    """The command that (re)installs the package with `args`, however it was installed."""
    if IN_UV_TOOL:
        return f'uv tool install --force "{TOOL_SPEC}"'
    return f"uv pip install {args}" if shutil.which("uv") else f"python -m pip install {args}"


def check() -> list[tuple[str, str, str | None]]:
    """Return (status, message, fix) per check; status is ok, warn or fail."""
    results: list[tuple[str, str, str | None]] = []

    age = (date.today() - date(*map(int, YT_DLP_VERSION.split(".")[:3]))).days
    if age > YT_DLP_MAX_AGE_DAYS:
        fix = (
            "uv tool upgrade creator-skill" if IN_UV_TOOL else _install('-U "yt-dlp[default,deno]"')
        )
        results.append(("warn", f"yt-dlp {YT_DLP_VERSION} is {age} days old", fix))
    else:
        results.append(("ok", f"yt-dlp {YT_DLP_VERSION}", None))

    deno = Path(sys.executable).parent / "deno"
    if importlib.util.find_spec("yt_dlp_ejs") and (deno.exists() or shutil.which("deno")):
        results.append(("ok", "deno + yt-dlp-ejs (needed for YouTube)", None))
    else:
        fix = _install('"yt-dlp[default,deno]"')
        results.append(("fail", "deno or yt-dlp-ejs missing (needed for YouTube)", fix))

    if transcribe.backend() == "mlx-whisper":
        results.append(("ok", "Whisper backend: mlx-whisper (Apple Silicon GPU)", None))
    else:
        tip = None
        if transcribe.APPLE_SILICON and not importlib.util.find_spec("mlx_whisper"):
            tip = _install('-e ".[mac]"') + "  # optional: much faster on Apple Silicon"
        elif transcribe.APPLE_SILICON:  # mlx-whisper is installed but needs the ffmpeg binary
            tip = "brew install ffmpeg  # optional: turns on mlx-whisper (faster)"
        results.append(("warn" if tip else "ok", "Whisper backend: faster-whisper (CPU)", tip))
    return results


def main() -> int:
    """Print the report; exit 1 if anything failed."""
    print(f"Checking environment ({platform.system()}, Python {platform.python_version()})\n")
    failed = False
    for status, message, fix in check():
        print(f"  [{status.upper():>4}] {message}")
        if fix:
            print(f"         fix: {fix}")
        failed = failed or status == "fail"
    print("\nAll good." if not failed else "\nFix the items above, then run: creator-skill doctor")
    return int(failed)

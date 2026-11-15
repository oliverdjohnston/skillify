"""Environment check: report what's missing and print the exact command to fix it."""

import importlib.util
import platform
import shutil
import sys
from datetime import date
from pathlib import Path

YT_DLP_MAX_AGE_DAYS = 45  # YouTube/TikTok break old yt-dlp releases within weeks


def _os_name() -> str:
    system = platform.system()
    if system != "Linux":
        return {"Darwin": "macOS"}.get(system, system)
    try:
        release = Path("/etc/os-release").read_text().lower()
    except OSError:
        return "Linux"
    return "Fedora" if "fedora" in release or "rhel" in release else "Debian"


SYSTEM_FIXES = {
    "python": {
        "macOS": "brew install python@3.12",
        "Debian": "sudo apt install python3.12 python3.12-venv",
        "Fedora": "sudo dnf install python3.12",
        "Windows": "winget install Python.Python.3.12",
    },
    "ffmpeg": {
        "macOS": "brew install ffmpeg",
        "Debian": "sudo apt update && sudo apt install ffmpeg",
        "Fedora": "sudo dnf install ffmpeg",
        "Windows": "winget install ffmpeg",
    },
}


def _pip(args: str) -> str:
    return f"uv pip install {args}" if shutil.which("uv") else f"python -m pip install {args}"


def check() -> list[tuple[str, str, str | None]]:
    """Return (status, message, fix) per check; status is ok, warn or fail."""
    os_name = _os_name()
    results: list[tuple[str, str, str | None]] = []

    py = ".".join(map(str, sys.version_info[:3]))
    if sys.version_info >= (3, 11):  # noqa: UP036 - doctor.py also runs under a bare interpreter
        results.append(("ok", f"Python {py}", None))
    else:
        results.append(("fail", f"Python {py} (need 3.11+)", SYSTEM_FIXES["python"].get(os_name)))

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        results.append(("ok", f"ffmpeg at {ffmpeg}", None))
    else:
        results.append(("fail", "ffmpeg not found", SYSTEM_FIXES["ffmpeg"].get(os_name)))

    try:
        from yt_dlp.version import __version__ as ytv

        age = (date.today() - date(*map(int, ytv.split(".")[:3]))).days
        if age > YT_DLP_MAX_AGE_DAYS:
            results.append(
                ("warn", f"yt-dlp {ytv} is {age} days old", _pip('-U "yt-dlp[default,deno]"'))
            )
        else:
            results.append(("ok", f"yt-dlp {ytv}", None))
    except ImportError:
        results.append(("fail", "yt-dlp not installed", _pip("-e .")))

    deno = Path(sys.executable).parent / "deno"
    has_ejs = importlib.util.find_spec("yt_dlp_ejs") is not None
    if has_ejs and (deno.exists() or shutil.which("deno")):
        results.append(("ok", "deno + yt-dlp-ejs (needed for YouTube)", None))
    else:
        results.append(
            (
                "fail",
                "deno or yt-dlp-ejs missing (needed for YouTube)",
                _pip('"yt-dlp[default,deno]"'),
            )
        )

    apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"
    has_mlx = importlib.util.find_spec("mlx_whisper") is not None
    if has_mlx and apple_silicon:
        results.append(("ok", "Whisper backend: mlx-whisper (Apple Silicon GPU)", None))
    elif importlib.util.find_spec("faster_whisper"):
        tip = _pip('-e ".[mac]"') + "  # optional, much faster" if apple_silicon else None
        results.append(("ok" if not tip else "warn", "Whisper backend: faster-whisper (CPU)", tip))
    else:
        results.append(("fail", "no Whisper backend installed", _pip("-e .")))
    return results


def main() -> int:
    """Print the report; exit 1 if anything failed."""
    print(f"Checking environment ({_os_name()})\n")
    failed = False
    for status, message, fix in check():
        print(f"  [{status.upper():>4}] {message}")
        if fix:
            print(f"         fix: {fix}")
        failed = failed or status == "fail"
    print("\nAll good." if not failed else "\nFix the items above, then run: creator-skill doctor")
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())

"""Transition sound effects: whoosh khud FFmpeg se banta hai (koi file download nahi)."""
import subprocess
from pathlib import Path


def whoosh_args(out_path, duration: float = 0.5) -> list[str]:
    fade_out = max(duration - 0.25, 0.05)
    return [
        "-y", "-f", "lavfi", "-i", f"anoisesrc=d={duration}:c=pink:a=0.5",
        "-af", f"highpass=f=300,lowpass=f=5000,afade=t=in:d=0.15,afade=t=out:st={fade_out:.2f}:d=0.25",
        "-ar", "44100", "-ac", "2", str(out_path),
    ]


def ensure_whoosh(cache_dir, runner=subprocess.run) -> Path | None:
    out = Path(cache_dir) / "whoosh.wav"
    if out.exists() and out.stat().st_size > 0:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = runner(["ffmpeg", "-hide_banner", "-loglevel", "error", *whoosh_args(out)],
                   capture_output=True, text=True)
    except OSError:
        return None
    if getattr(r, "returncode", 1) != 0 or not out.exists():
        return None
    return out


def transition_starts(durations: list[float], transition: float, lead: float = 0.1) -> list[float]:
    """Har xfade transition ka waqt (video ke andar), thora pehle taake whoosh theek par ho."""
    starts, total = [], 0.0
    for i, d in enumerate(durations[:-1]):
        total += d
        offset = total - (i + 1) * transition
        starts.append(round(max(offset - lead, 0.0), 3))
    return starts

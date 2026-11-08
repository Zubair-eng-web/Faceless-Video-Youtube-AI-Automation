"""Live test: asli FFmpeg par ducking + sfx wala audio graph chalakar dekhna ke syntax theek hai."""
import subprocess
import sys
from pathlib import Path

from app.services.audio_mix import FMT, build_audio_graph, sfx_filters
from app.services.sfx import ensure_whoosh, transition_starts

root = Path(__file__).resolve().parent.parent
out_dir = root / "output" / "audio_test"
out_dir.mkdir(parents=True, exist_ok=True)

whoosh = ensure_whoosh(root / "assets" / "cache" / "sfx")
if whoosh is None:
    print("[FAIL] whoosh nahi bana (ffmpeg PATH mein hai?)")
    sys.exit(1)
print("[OK] whoosh:", whoosh)

starts = transition_starts([3, 3, 3], 0.5)
parts = [f"[0:a]{FMT}[voice]", f"[1:a]{FMT},volume=0.25,afade=t=out:st=6:d=1.5[music]"]
sx, label = sfx_filters(starts, 2)
parts += sx
parts += build_audio_graph("voice", "music", label)

out = out_dir / "mix.wav"
cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
       "-f", "lavfi", "-t", "8", "-i", "sine=frequency=220",
       "-f", "lavfi", "-t", "30", "-i", "sine=frequency=440",
       "-i", str(whoosh),
       "-filter_complex", ";".join(parts), "-map", "[aout]", "-t", "8", str(out)]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0 or not out.exists():
    print("[FAIL] ffmpeg error:\n", r.stderr)
    sys.exit(1)
print(f"[OK] mix bana: {out} ({out.stat().st_size} bytes), sfx waqt: {starts}")

"""Live test: nakli logo ko asli FFmpeg se test video par lagana."""
import subprocess
import sys
from pathlib import Path

from app.services.branding import logo_overlay_filters

root = Path(__file__).resolve().parent.parent
out_dir = root / "output" / "branding_test"
out_dir.mkdir(parents=True, exist_ok=True)
logo = out_dir / "logo.png"
out = out_dir / "branded.mp4"


def ff(*args):
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], capture_output=True, text=True)
    if r.returncode != 0:
        print("[FAIL] ffmpeg:\n", r.stderr)
        sys.exit(1)


ff("-f", "lavfi", "-i", "color=c=red:s=300x300", "-frames:v", "1", str(logo))
parts = logo_overlay_filters("0:v", 1, "vout", 1080, "top-right", 0.8, 0.18)
parts[1] = parts[1].replace("[0:v]", "[0:v]")  # label pehle se bracket mein hai
fc = ";".join([parts[0], parts[1].replace("[[0:v]]", "[0:v]")])
ff("-f", "lavfi", "-t", "3", "-i", "testsrc2=s=1080x1920:r=30", "-i", str(logo),
   "-filter_complex", fc, "-map", "[vout]", "-pix_fmt", "yuv420p", str(out))
print(f"[OK] logo laga: {out} ({out.stat().st_size} bytes). Video kholein, upar daayen laal chaukor dikhna chahiye.")

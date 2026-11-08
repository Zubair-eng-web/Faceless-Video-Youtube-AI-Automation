import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
p = root / "scripts" / "try_video.py"
lines = p.read_text(encoding="utf-8").splitlines()

i = next((k for k, l in enumerate(lines) if "music_dir.glob" in l and "music" in l.split("=")[0]), None)
if i is None or "Music" not in lines[i + 1]:
    print("[FAIL] music wali lines nahi mili. Kuch nahi badla.")
    raise SystemExit(1)

shutil.copy(p, root / "output" / "try_video.bak")
ind = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
new = [
    ind + "from app.services.music import list_tracks",
    ind + "_tracks = list_tracks(settings.music_dir)",
    ind + "_count = sum(len(v) for v in _tracks.values())",
    ind + 'print("Music   :", f"{_count} track(s) mile, moods: {\', \'.join(sorted(_tracks))}" if _count else "nahi mili (assets/music khali hai)")',
]
lines[i:i + 2] = new
p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("[OK] try_video.py theek ho gayi")

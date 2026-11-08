import re, shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
p = root / "scripts" / "try_video.py"
t = p.read_text(encoding="utf-8")
shutil.copy(p, root / "output" / "try_video.bak")

old = re.search(r'^music = list\(settings\.music_dir\.glob\("\*\.mp3"\)\) \+ list\(settings\.music_dir\.glob\("\*\.wav"\)\)\n'
                r'print\("Music   :".*\)\n', t, re.M)
if not old:
    print("[FAIL] music wali lines nahi mili. Kuch nahi badla.")
    raise SystemExit(1)

new = '''from app.services.music import list_tracks
_tracks = list_tracks(settings.music_dir)
_count = sum(len(v) for v in _tracks.values())
print("Music   :", f"{_count} track(s) mile, moods: {', '.join(sorted(_tracks))}" if _count
      else "nahi mili (assets\\\\music khali hai)")
'''
t = t[:old.start()] + new + t[old.end():]
p.write_text(t, encoding="utf-8")
print("[OK] try_video.py theek ho gayi")

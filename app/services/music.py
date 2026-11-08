"""Mood ke hisab se background music chunna.

Tracks ki tartib (dono tareeqe chalte hain):
  assets/music/calm/track.mp3        (mood ka folder)
  assets/music/calm_track.mp3        (file ke naam ka pehla lafz mood)
Jis track par mood nahi, wo "any" mein jata hai.
"""
import random
import re
from pathlib import Path

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg"}
MOODS = ("calm", "upbeat", "dramatic", "mysterious", "inspiring")

KEYWORDS = {
    "dramatic": ["shocking", "war", "danger", "deadly", "disaster", "explosion", "crash", "terrifying", "dark"],
    "mysterious": ["mystery", "mysterious", "secret", "hidden", "unknown", "ancient", "strange", "unexplained"],
    "calm": ["ocean", "nature", "sleep", "relax", "peaceful", "forest", "rain", "calm"],
    "upbeat": ["fun", "amazing", "funny", "party", "best", "top ", "hack", "trick", "crazy"],
    "inspiring": ["success", "motivation", "dream", "growth", "habit", "mindset", "discipline", "inspire"],
}


def track_mood(path, root) -> str | None:
    p = Path(path)
    try:
        rel = p.relative_to(root)
        if len(rel.parts) > 1 and rel.parts[0].lower() in MOODS:
            return rel.parts[0].lower()
    except ValueError:
        pass
    prefix = re.split(r"[_\- ]", p.stem.lower())[0]
    return prefix if prefix in MOODS else None


def list_tracks(music_dir) -> dict[str, list[Path]]:
    root = Path(music_dir)
    out: dict[str, list[Path]] = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in AUDIO_EXT:
            out.setdefault(track_mood(p, root) or "any", []).append(p)
    return out


def mood_from_text(text: str, default: str = "calm") -> str:
    low = (text or "").lower()
    scores = {m: sum(low.count(k) for k in kws) for m, kws in KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else default


def pick_track(music_dir, mood: str | None = None, rng=random) -> Path | None:
    tracks = list_tracks(music_dir)
    if not tracks:
        return None
    pool = tracks.get(mood, []) if mood else []
    if not pool:
        pool = tracks.get("any", []) or [p for v in tracks.values() for p in v]
    return rng.choice(pool)

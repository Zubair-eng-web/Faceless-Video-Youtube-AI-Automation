"""Quality checker: video ki technical jaanch (ffmpeg), captions aur visuals."""
import json
import re
import subprocess
from pathlib import Path

from pydantic import BaseModel

from app.core.models import Storyboard
from app.services.pixabay import SceneClip
from app.services.tts import Voiceover

BLACK_MIN_SECONDS = 0.5
SILENCE_MIN_SECONDS = 1.5
QUIET_DB = -30.0
DURATION_TOLERANCE = 0.5

BLACK_RE = re.compile(r"black_start:\s*(-?[\d.]+)\s+black_end:\s*(-?[\d.]+)")
SILENCE_START_RE = re.compile(r"silence_start:\s*(-?[\d.]+)")
SILENCE_END_RE = re.compile(r"silence_end:\s*(-?[\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)")
MEAN_VOLUME_RE = re.compile(r"mean_volume:\s*(-?[\d.]+|-inf)\s*dB")


class QualityError(RuntimeError):
    pass


class Issue(BaseModel):
    level: str  # "error" ya "warning"
    code: str
    message: str


class QualityReport(BaseModel):
    issues: list[Issue] = []
    stats: dict = {}

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def passed(self) -> bool:
        return not self.errors


def parse_black_segments(log: str) -> list[tuple[float, float]]:
    return [(float(a), float(b)) for a, b in BLACK_RE.findall(log)]


def parse_silences(log: str, total_duration: float) -> list[tuple[float, float]]:
    """(start, duration) ki list. Agar khamoshi file ke aakhir tak chali ho to wo bhi shamil."""
    result: list[tuple[float, float]] = []
    open_start = None
    for line in log.splitlines():
        end_match = SILENCE_END_RE.search(line)
        if end_match:
            end, duration = float(end_match.group(1)), float(end_match.group(2))
            result.append((round(end - duration, 3), duration))
            open_start = None
            continue
        start_match = SILENCE_START_RE.search(line)
        if start_match:
            open_start = float(start_match.group(1))
    if open_start is not None and total_duration > open_start:
        result.append((open_start, round(total_duration - open_start, 3)))
    return result


def parse_mean_volume(log: str) -> float | None:
    match = MEAN_VOLUME_RE.search(log)
    return float(match.group(1)) if match else None


def _ass_seconds(text: str) -> float:
    h, m, s = text.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_ass_dialogues(text: str) -> list[tuple[float, float]]:
    result = []
    for line in text.splitlines():
        if line.startswith("Dialogue:"):
            parts = line.split(",", 9)
            result.append((_ass_seconds(parts[1]), _ass_seconds(parts[2])))
    return result


def probe_media(path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise QualityError(f"ffprobe fail: {result.stderr.strip()[-300:]}")
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise QualityError("Video stream nahi mili")
    return {
        "width": int(video["width"]),
        "height": int(video["height"]),
        "duration": float(data["format"]["duration"]),
        "has_audio": any(s.get("codec_type") == "audio" for s in streams),
    }


def analyze_media(path) -> str:
    """Ek hi pass me black frames, khamoshi aur awaaz ki level (ffmpeg ka log wapas deta hai)."""
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-nostdin", "-i", str(path),
         "-vf", f"blackdetect=d={BLACK_MIN_SECONDS}:pix_th=0.10",
         "-af", f"silencedetect=noise=-40dB:d={SILENCE_MIN_SECONDS},volumedetect",
         "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise QualityError(f"ffmpeg analysis fail: {result.stderr.strip()[-300:]}")
    return result.stderr


def check_video(
    video_path,
    voiceover: Voiceover,
    board: Storyboard,
    clips: list[SceneClip],
    captions_path,
    expected_size: tuple[int, int] = (1080, 1920),
    probe=probe_media,
    analyze=analyze_media,
) -> QualityReport:
    issues: list[Issue] = []
    stats: dict = {}

    def add(level: str, code: str, message: str) -> None:
        issues.append(Issue(level=level, code=code, message=message))

    path = Path(video_path)
    if not path.exists() or path.stat().st_size == 0:
        add("error", "missing_file", "Video file nahi mili ya khali hai")
        return QualityReport(issues=issues, stats=stats)
    stats["size_mb"] = round(path.stat().st_size / 1_000_000, 1)

    # --- Visuals: har scene ki clip maujood honi chahiye ---
    scene_seconds = {s.number: s.duration for s in voiceover.scenes}
    by_scene = {c.scene_number: c for c in clips}
    for scene in board.scenes:
        clip = by_scene.get(scene.number)
        if clip is None:
            add("error", "missing_clip", f"Scene {scene.number} ki clip nahi hai")
        elif not Path(clip.path).exists():
            add("error", "clip_file", f"Scene {scene.number} ki clip ki file disk par nahi")
        elif clip.duration < scene_seconds.get(scene.number, scene.duration):
            add("warning", "clip_short",
                f"Scene {scene.number}: clip ({clip.duration:.0f}s) scene se chhoti hai, loop hogi")

    # --- Technical jaanch ---
    try:
        info = probe(path)
    except Exception as exc:
        add("error", "probe_failed", f"Video parhi nahi ja saki: {exc}")
        return QualityReport(issues=issues, stats=stats)
    stats.update(width=info["width"], height=info["height"], duration=round(info["duration"], 2))

    if (info["width"], info["height"]) != tuple(expected_size):
        add("error", "resolution",
            f"Size {info['width']}x{info['height']} hai, {expected_size[0]}x{expected_size[1]} chahiye")
    if not info["has_audio"]:
        add("error", "no_audio", "Video me audio track nahi hai")
    diff = abs(info["duration"] - voiceover.duration)
    if diff > DURATION_TOLERANCE:
        add("error", "duration",
            f"Video {info['duration']:.1f}s hai lekin voiceover {voiceover.duration:.1f}s ka hai")

    try:
        log = analyze(path)
    except Exception as exc:
        add("error", "analysis_failed", f"Video ki jaanch fail: {exc}")
        log = None

    if log is not None:
        black = [(s, e) for s, e in parse_black_segments(log) if e - s >= BLACK_MIN_SECONDS]
        stats["black_segments"] = len(black)
        for start, end in black:
            add("error", "black_frames", f"Kala screen {start:.1f}s se {end:.1f}s tak")

        if info["has_audio"]:
            silences = [(s, d) for s, d in parse_silences(log, info["duration"]) if d >= SILENCE_MIN_SECONDS]
            stats["long_silences"] = len(silences)
            for start, duration in silences:
                add("warning", "long_silence", f"{duration:.1f}s ki khamoshi {start:.1f}s par")

            mean = parse_mean_volume(log)
            if mean is not None:
                stats["mean_volume_db"] = mean
                if mean == float("-inf"):
                    add("error", "silent_audio", "Audio bilkul khamosh hai")
                elif mean < QUIET_DB:
                    add("warning", "quiet_audio", f"Awaaz bohat halki hai ({mean:.1f} dB)")

    # --- Captions ---
    cpath = Path(captions_path)
    if not cpath.exists():
        add("error", "no_captions", "Captions file nahi mili")
    else:
        lines = parse_ass_dialogues(cpath.read_text(encoding="utf-8"))
        expected = len([w for w in voiceover.words if w.text.strip()])
        stats["caption_lines"] = len(lines)
        if len(lines) != expected:
            add("error", "caption_count", f"Captions {len(lines)} hain lekin lafz {expected} hain")
        starts = [s for s, _ in lines]
        if starts != sorted(starts):
            add("error", "caption_order", "Captions ka waqt aage peeche hai")
        if lines and max(e for _, e in lines) > info["duration"] + DURATION_TOLERANCE:
            add("error", "caption_late", "Captions video ke khatam hone ke baad tak chal rahe hain")

    return QualityReport(issues=issues, stats=stats)

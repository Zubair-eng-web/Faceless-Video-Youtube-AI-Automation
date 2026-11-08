"""Long-form QA: approval se pehle actionable failures ki report."""
import json
import re
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from app.services.long_script import LongScript
from app.services.long_visuals import build_visual_report
from app.services.pixabay import SceneClip
from app.services.quality import parse_black_segments
from app.services.tts import Voiceover
from app.services.video_editor import probe_video

MAX_SCENE_SECONDS = 20.0
MAX_SILENCE = 4.0
MAX_SPREAD_DB = 6.0


class QAIssue(BaseModel):
    level: str  # error | warning
    area: str
    msg: str
    fix: str = ""
    scene: int | None = None


class QAReport(BaseModel):
    issues: list[QAIssue] = Field(default_factory=list)
    stats: dict = Field(default_factory=dict)

    @property
    def errors(self) -> list[QAIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[QAIssue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{len(self.errors)} error, {len(self.warnings)} warning " + ("(approve ke liye tayyar)" if self.ok else "(pehle fix karein)")


def load_long_run(run, scenes: int = 0):
    """Run folder se script, board, clips, voiceover (pehle `scenes` scenes; 0 = sab)."""
    run = Path(run)
    need = [run / "long_script.json", run / "clips.json", run / "narration" / "voiceover.json"]
    for p in need:
        if not p.is_file():
            raise FileNotFoundError(f"{p} nahi mili. Pehle script, voiceover aur clips banayen.")
    script = LongScript.model_validate_json(need[0].read_text(encoding="utf-8"))
    allsc = script.storyboard.scenes
    count = len(allsc) if scenes == 0 else min(scenes, len(allsc))
    board = script.storyboard.model_copy(update={"scenes": allsc[:count]})
    nums = {s.number for s in board.scenes}
    data = json.loads(need[1].read_text(encoding="utf-8"))
    items = list(data.values()) if isinstance(data, dict) else data
    clips = [c for c in (SceneClip.model_validate(i) for i in items) if c.scene_number in nums]
    vo = Voiceover.model_validate_json(need[2].read_text(encoding="utf-8"))
    vo = vo.model_copy(update={"scenes": [s for s in vo.scenes if s.number in nums]})
    return script, board, clips, vo


def _issue(level, area, msg, fix="", scene=None):
    return QAIssue(level=level, area=area, msg=msg, fix=fix, scene=scene)


def check_coverage(board, clips, voiceover) -> list[QAIssue]:
    out = []
    by_clip = {c.scene_number: c for c in clips}
    voiced = {s.number for s in voiceover.scenes}
    for s in board.scenes:
        c = by_clip.get(s.number)
        if c is None:
            out.append(_issue("error", "coverage", "Clip nahi mili", "python -m scripts.try_long_clips", s.number))
        elif not Path(c.path).is_file():
            out.append(_issue("error", "coverage", "Clip file disk par nahi", "try_long_clips dobara chalayen", s.number))
        if s.number not in voiced:
            out.append(_issue("error", "coverage", "Narration nahi bani", "python -m scripts.try_long_voice", s.number))
    return out


def check_timing(voiceover) -> list[QAIssue]:
    out, sc = [], voiceover.scenes
    for v in sc:
        n = len(v.words)
        if v.duration > MAX_SCENE_SECONDS:
            out.append(_issue("warning", "timing", f"Scene {v.duration:.0f}s ka hai", "Script mein scene chhota karein ya visual badlein", v.number))
        if n >= 5 and v.duration > 0:
            wpm = n / v.duration * 60
            if wpm > 220:
                out.append(_issue("warning", "timing", f"Narration bohat tez ({wpm:.0f} wpm)", "Scene ka text chhota karein", v.number))
            elif wpm < 80:
                out.append(_issue("warning", "timing", f"Narration bohat dheemi ({wpm:.0f} wpm)", "Scene ka text barhayein ya voice rate check karein", v.number))
    for a, b in zip(sc, sc[1:]):
        gap = b.start_offset - (a.start_offset + a.duration)
        if gap > 1.5 or gap < -0.05:
            out.append(_issue("warning", "timing", f"Scene {a.number} aur {b.number} ke beech {gap:+.2f}s ka gap", "Narration dobara banayein", a.number))
    return out


def check_captions(board, voiceover) -> list[QAIssue]:
    out = []
    narr = {s.number: len(s.narration.split()) for s in board.scenes}
    for v in voiceover.scenes:
        ws = v.words
        if not ws:
            out.append(_issue("error", "captions", "Caption words nahi", "Narration dobara banayein", v.number))
            continue
        bad = sum(1 for a, b in zip(ws, ws[1:]) if b.start < a.start - 0.01) + sum(1 for w in ws if w.end <= w.start)
        if bad:
            out.append(_issue("warning", "captions", f"{bad} word timings ghalat", "Narration dobara banayein", v.number))
        if ws[-1].end > v.duration + 0.5:
            out.append(_issue("warning", "captions", "Caption scene ke baad tak chalta hai", "Narration dobara banayein", v.number))
        n = narr.get(v.number, 0)
        if n and abs(len(ws) - n) > max(3, 0.25 * n):
            out.append(_issue("warning", "captions", f"Caption words ({len(ws)}) narration ({n}) se match nahi", "Scene ka text aur voice check karein", v.number))
        span = ws[-1].end - ws[0].start
        if span > 0 and len(ws) / span > 5.0:
            out.append(_issue("warning", "captions", "Caption padhne ke liye bohat tez", "Scene ka text chhota karein", v.number))
    return out


def parse_audio_stats(stderr: str) -> dict:
    mean = re.search(r"mean_volume:\s*(-?[\d.]+)\s*dB", stderr or "")
    peak = re.search(r"max_volume:\s*(-?[\d.]+)\s*dB", stderr or "")
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", stderr or "")]
    durs = [float(x) for x in re.findall(r"silence_duration:\s*([\d.]+)", stderr or "")]
    return {"mean_db": float(mean.group(1)) if mean else None, "peak_db": float(peak.group(1)) if peak else None,
            "silences": list(zip(starts, durs))}


def check_audio_stats(st: dict) -> list[QAIssue]:
    out = []
    mean, peak = st.get("mean_db"), st.get("peak_db")
    if mean is not None and mean < -30:
        out.append(_issue("warning", "audio", f"Awaaz bohat dheemi (mean {mean:.1f} dB)", "LONG_TARGET_LUFS barhayein"))
    if mean is not None and mean > -12:
        out.append(_issue("warning", "audio", f"Awaaz bohat tez (mean {mean:.1f} dB)", "LONG_TARGET_LUFS kam karein"))
    if peak is not None and peak >= -0.1:
        out.append(_issue("warning", "audio", f"Clipping ka khatra (peak {peak:.1f} dB)", "Music volume ya LONG_TARGET_LUFS kam karein"))
    for start, dur in st.get("silences", []):
        if dur >= MAX_SILENCE:
            out.append(_issue("warning", "audio", f"{dur:.1f}s ki khamoshi {start:.0f}s par", "Is hisse ki narration check karein"))
    return out


def analyze_audio(path) -> dict:
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(path), "-vn", "-af",
                        f"volumedetect,silencedetect=n=-45dB:d={MAX_SILENCE}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return parse_audio_stats(r.stderr)


def find_black(path) -> list:
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-i", str(path), "-vf",
                        "scale=320:-2,blackdetect=d=0.5:pix_th=0.08", "-an", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return parse_black_segments(r.stderr or "")


def check_long_quality(script, board, clips, voiceover, run_dir, video_path, skip_black=False,
                       audio_fn=analyze_audio, black_fn=find_black, probe_fn=probe_video) -> QAReport:
    rep = QAReport()
    rep.issues += check_coverage(board, clips, voiceover)
    rep.issues += check_timing(voiceover)
    rep.issues += check_captions(board, voiceover)
    for w in build_visual_report(board, clips).warnings:
        rep.issues.append(_issue("warning", "visual", str(w), "try_long_clips dobara chalayen ya script ki search_query badlein"))
    if len({s.voice for s in []}) > 1:
        pass
    video = Path(video_path)
    if not video.is_file():
        rep.issues.append(_issue("error", "render", "video.mp4 nahi mili", "python -m scripts.try_long_render"))
    else:
        info = probe_fn(video)
        rep.stats["duration"] = round(info["duration"], 2)
        if info["width"] * 9 != info["height"] * 16:
            rep.issues.append(_issue("error", "render", f"Video {info['width']}x{info['height']} hai, 16:9 chahiye", "Dobara render karein"))
        if voiceover.scenes:
            expected = max(s.start_offset + s.duration for s in voiceover.scenes)
            if abs(info["duration"] - expected) > 0.5:
                rep.issues.append(_issue("error", "timing", f"Video {info['duration']:.1f}s, narration {expected:.1f}s", "Render dobara chalayen"))
        st = audio_fn(video)
        rep.stats["audio"] = st
        rep.issues += check_audio_stats(st)
        if not skip_black:
            black = black_fn(video)
            rep.stats["black_segments"] = len(black)
            for a, b in black:
                rep.issues.append(_issue("warning", "transitions", f"Kala frame {a:.1f}s se {b:.1f}s tak", "Us scene ki clip badlein"))
        if len(board.scenes) == len(script.storyboard.scenes) and script.minutes:
            ratio = info["duration"] / (script.minutes * 60)
            if not 0.75 <= ratio <= 1.3:
                rep.issues.append(_issue("warning", "episode", f"Lambai target ({script.minutes:.0f} min) se {ratio:.2f}x hai", "Script ko target ke qareeb layein"))
    nr = Path(run_dir) / "narration" / "narration_report.json"
    if nr.is_file():
        data = json.loads(nr.read_text(encoding="utf-8"))
        spread = data.get("loudness_spread_db")
        if spread is not None and spread > MAX_SPREAD_DB:
            rep.issues.append(_issue("warning", "episode", f"Scenes ki awaaz ka farq {spread:.1f} dB", "Narration dobara banayein"))
        for w in data.get("warnings", []):
            rep.issues.append(_issue("warning", "narration", str(w)))
    (Path(run_dir) / "long_quality.json").write_text(rep.model_dump_json(indent=2), encoding="utf-8")
    return rep

"""Long-form narration: pronunciation, pauses, loudness balance, resume aur report.

Shorts wali tts.py ko chhede baghair, uske helpers use karta hai. Har scene ka naap/gain/pause ek hi ffmpeg
call mein lagta hai, aur har scene ka nateeja scene_NNN.json mein save hota hai (resume).
Settings: LONG_VOICE, LONG_VOICE_RATE, LONG_SCENE_PAUSE, LONG_CHAPTER_PAUSE, LONG_TARGET_LUFS.
"""
import re
import statistics
import subprocess
import time
from pathlib import Path

from pydantic import BaseModel, Field

from app.services.long_script import LongScript, _env, _raw, word_count
from app.services.tts import (SceneAudio, TTSError, Voiceover, _synth_with_retry, audio_duration, concat_audio,
                              edge_synthesize, fallback_word_timings, pick_voice, shift_words, silence_trim,
                              trim_audio)

MIN_WPM, MAX_WPM = 100, 230
MAX_SPREAD_DB = 6.0


class NarrationConfig(BaseModel):
    voice: str | None = None
    rate: str = "+0%"
    scene_pause: float = 0.15
    chapter_pause: float = 0.7
    target_lufs: float = -16.0
    max_gain_db: float = 6.0

    @classmethod
    def from_env(cls) -> "NarrationConfig":
        rate = (_raw("LONG_VOICE_RATE") or "+0%").strip()
        if not re.fullmatch(r"[+-]\d{1,3}%", rate):
            rate = "+0%"
        return cls(voice=_raw("LONG_VOICE") or None, rate=rate,
                   scene_pause=_env("LONG_SCENE_PAUSE", 0.15, float),
                   chapter_pause=_env("LONG_CHAPTER_PAUSE", 0.7, float),
                   target_lufs=_env("LONG_TARGET_LUFS", -16.0, float))


_RULES = [
    (r"\$(\d[\d,.]*)\s?(million|billion|trillion)\b", r"\1 \2 dollars"),
    (r"\$(\d[\d,]*(?:\.\d+)?)", r"\1 dollars"),
    (r"(\d)\s?%", r"\1 percent"),
    (r"\bkm/h\b", "kilometers per hour"),
    (r"\bkm/s\b", "kilometers per second"),
    (r"\bmph\b", "miles per hour"),
    (r"(\d)\s?km\b", r"\1 kilometers"),
    (r"(\d)\s?kg\b", r"\1 kilograms"),
    (r"\s?\u00b0\s?C\b", " degrees Celsius"),
    (r"\s?\u00b0\s?F\b", " degrees Fahrenheit"),
    (r"\s?\u00b0", " degrees"),
    (r"\be\.g\.,?", "for example,"),
    (r"\bi\.e\.,?", "that is,"),
    (r"\bvs\.?(?=\s)", "versus"),
    (r"\bapprox\.", "approximately"),
    (r"\s&\s", " and "),
]


def prepare_text(text: str, language: str = "English") -> str:
    """TTS ke liye text: English mein numbers/abbreviations bolne layak, baqi zabanon mein sirf safai."""
    text = re.sub(r"[*#_`]+", "", text or "")
    if (language or "").strip().lower() == "english":
        for pattern, repl in _RULES:
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return " ".join(text.split())


def parse_mean_volume(stderr: str):
    m = re.search(r"mean_volume:\s*(-?[\d.]+)\s*dB", stderr or "")
    return float(m.group(1)) if m else None


def _ffmpeg(args, what):
    r = subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise TTSError(f"ffmpeg {what} fail: {r.stderr.strip()[-300:]}")


def measure_volume(path):
    r = subprocess.run(["ffmpeg", "-nostdin", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    return parse_mean_volume(r.stderr)


def process_scene(path, gain_db: float, pad_seconds: float) -> None:
    """Awaaz ka gain aur aakhir mein khamoshi, ek hi ffmpeg call mein."""
    path = Path(path)
    filters = []
    if abs(gain_db) >= 0.05:
        filters.append(f"volume={gain_db:.2f}dB")
    if pad_seconds > 0:
        filters.append(f"apad=pad_dur={pad_seconds:.3f}")
    if not filters:
        return
    tmp = path.with_suffix(".proc.mp3")
    try:
        _ffmpeg(["-i", str(path), "-af", ",".join(filters), "-c:a", "libmp3lame", "-q:a", "2", str(tmp)],
                "scene process")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def normalize_loudness(path, lufs: float) -> None:
    path = Path(path)
    tmp = path.with_suffix(".norm.mp3")
    try:
        _ffmpeg(["-i", str(path), "-af", f"loudnorm=I={lufs}:TP=-1.5:LRA=11", "-ar", "44100",
                 "-c:a", "libmp3lame", "-q:a", "2", str(tmp)], "loudnorm")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


class SceneMeta(BaseModel):
    audio: SceneAudio
    mean_db: float | None = None
    processed: bool = False
    spoken: str = ""


class NarrationReport(BaseModel):
    voice: str = ""
    rate: str = "+0%"
    scenes: int = 0
    duration: float = 0.0
    target_seconds: float | None = None
    loudness_spread_db: float | None = None
    gains_applied: int = 0
    slow_scenes: list[int] = Field(default_factory=list)
    fast_scenes: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def summary(self) -> str:
        spread = f"{self.loudness_spread_db:.1f} dB" if self.loudness_spread_db is not None else "?"
        return (f"{self.scenes} scenes, {self.duration / 60:.1f} min, awaaz ka farq {spread}, "
                f"{self.gains_applied} scenes balance, {len(self.slow_scenes)} dheemi, {len(self.fast_scenes)} tez")


def _load_meta(path):
    try:
        return SceneMeta.model_validate_json(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def generate_long_voiceover(script: LongScript, out_dir, cfg=None, max_scenes=None, synth=edge_synthesize,
                            duration_fn=audio_duration, trim_fn=trim_audio, measure_fn=measure_volume,
                            process_fn=process_scene, concat_fn=concat_audio, normalize_fn=normalize_loudness,
                            max_attempts=3, sleep=time.sleep, progress=print):
    """(Voiceover, NarrationReport). Folder mein scene_NNN.mp3/json, voiceover.mp3/json, narration_report.json."""
    cfg = cfg or NarrationConfig.from_env()
    board = script.storyboard
    scenes = board.scenes[:max_scenes]
    if not scenes:
        raise TTSError("Script mein koi scene nahi")
    voice = pick_voice(board.language, cfg.voice)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    metas: list[SceneMeta] = []

    # Phase 1: awaaz banao, faltu khamoshi kaato, loudness naapo (resume ke saath)
    for i, sc in enumerate(scenes, 1):
        mp3, js = out / f"scene_{sc.number:03d}.mp3", out / f"scene_{sc.number:03d}.json"
        meta = _load_meta(js)
        if meta and mp3.exists():
            metas.append(meta)
            continue
        spoken = prepare_text(sc.narration, board.language)
        words = _synth_with_retry(synth, spoken, voice, cfg.rate, mp3, max_attempts, sleep)
        duration = round(duration_fn(mp3), 3)
        if words:
            trim = silence_trim(words, duration)
            if trim:
                trim_fn(mp3, trim[0], trim[1])
                words = shift_words(words, -trim[0])
                duration = round(duration_fn(mp3), 3)
        else:
            words = fallback_word_timings(spoken, duration)
        meta = SceneMeta(audio=SceneAudio(number=sc.number, path=str(mp3), start_offset=0.0, duration=duration,
                                          words=words), mean_db=measure_fn(mp3), spoken=spoken)
        js.write_text(meta.model_dump_json(indent=2), encoding="utf-8")
        metas.append(meta)
        if i % 10 == 0:
            progress(f"Narration {i}/{len(scenes)}")

    # Phase 2: awaaz barabar karo aur pauses lagao
    levels = [m.mean_db for m in metas if m.mean_db is not None]
    median = statistics.median(levels) if levels else None
    chapter_ends = {c.last_scene for c in script.chapters}
    last_no = scenes[-1].number
    gains = 0
    for m in metas:
        if m.processed:
            continue
        no = m.audio.number
        gain = 0.0
        if median is not None and m.mean_db is not None:
            gain = max(-cfg.max_gain_db, min(cfg.max_gain_db, median - m.mean_db))
            gain = gain if abs(gain) >= 1.0 else 0.0
        pause = 0.0 if no == last_no else (cfg.chapter_pause if no in chapter_ends else cfg.scene_pause)
        if gain or pause > 0:
            process_fn(m.audio.path, gain, pause)
            m.audio = m.audio.model_copy(update={"duration": round(duration_fn(m.audio.path), 3)})
        gains += 1 if gain else 0
        m.processed = True
        (out / f"scene_{no:03d}.json").write_text(m.model_dump_json(indent=2), encoding="utf-8")

    offset = 0.0
    final: list[SceneAudio] = []
    for m in metas:
        final.append(m.audio.model_copy(update={"start_offset": round(offset, 3)}))
        offset += m.audio.duration
    full = out / "voiceover.mp3"
    concat_fn([Path(s.path) for s in final], full)
    normalize_fn(full, cfg.target_lufs)
    vo = Voiceover(path=str(full), voice=voice, duration=round(offset, 3), scenes=final)

    rep = NarrationReport(voice=voice, rate=cfg.rate, scenes=len(final), duration=vo.duration, gains_applied=gains)
    if len(levels) > 1:
        rep.loudness_spread_db = round(max(levels) - min(levels), 1)
        if rep.loudness_spread_db > MAX_SPREAD_DB:
            rep.warnings.append(f"Scenes ki awaaz mein {rep.loudness_spread_db} dB ka farq tha, balance kiya gaya")
    for s in final:
        if len(s.words) >= 4:
            span = s.words[-1].end - s.words[0].start
            wpm = len(s.words) / span * 60 if span > 0 else 0
            if wpm < MIN_WPM:
                rep.slow_scenes.append(s.number)
            elif wpm > MAX_WPM:
                rep.fast_scenes.append(s.number)
    if rep.slow_scenes:
        rep.warnings.append(f"{len(rep.slow_scenes)} scenes bohat dheeme: {rep.slow_scenes[:10]}")
    if rep.fast_scenes:
        rep.warnings.append(f"{len(rep.fast_scenes)} scenes bohat tez: {rep.fast_scenes[:10]}")
    if max_scenes is None and script.minutes:
        rep.target_seconds = round(script.minutes * 60, 1)
        ratio = vo.duration / rep.target_seconds
        if not 0.7 <= ratio <= 1.3:
            rep.warnings.append(f"Narration {vo.duration / 60:.1f} min ki hai, target {script.minutes:g} min")
    (out / "voiceover.json").write_text(vo.model_dump_json(indent=2), encoding="utf-8")
    (out / "narration_report.json").write_text(rep.model_dump_json(indent=2), encoding="utf-8")
    return vo, rep
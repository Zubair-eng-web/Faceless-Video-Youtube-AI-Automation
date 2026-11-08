"""Edge TTS voiceover: har scene ki audio, asli duration aur word-level timestamps."""
import asyncio
import subprocess
import time
from pathlib import Path

import edge_tts
from pydantic import BaseModel

from app.core.models import Storyboard

TICKS_PER_SECOND = 10_000_000  # Edge TTS offsets 100 nanosecond ticks me deta hai
DEFAULT_VOICE = "en-US-AndrewNeural"

VOICES = {
    "English": "en-US-AndrewNeural",
    "Hindi": "hi-IN-MadhurNeural",
    "Urdu": "ur-PK-AsadNeural",
    "Spanish": "es-ES-AlvaroNeural",
    "French": "fr-FR-HenriNeural",
    "Arabic": "ar-SA-HamedNeural",
}


class TTSError(RuntimeError):
    pass


class WordTiming(BaseModel):
    text: str
    start: float
    end: float


class SceneAudio(BaseModel):
    number: int
    path: str
    start_offset: float
    duration: float
    words: list[WordTiming]  # scene ke andar ka waqt (scene ke start se)


class Voiceover(BaseModel):
    path: str
    voice: str
    duration: float
    scenes: list[SceneAudio]

    @property
    def words(self) -> list[WordTiming]:
        """Poori video ke hisab se word timings."""
        result: list[WordTiming] = []
        for scene in self.scenes:
            result.extend(shift_words(scene.words, scene.start_offset))
        return result


def ticks_to_seconds(ticks: int) -> float:
    return round(ticks / TICKS_PER_SECOND, 3)


def shift_words(words: list[WordTiming], offset: float) -> list[WordTiming]:
    return [WordTiming(text=w.text, start=round(w.start + offset, 3), end=round(w.end + offset, 3)) for w in words]


def fallback_word_timings(text: str, duration: float) -> list[WordTiming]:
    """Agar Edge TTS ne word events na diye, to lafzon ki lambai ke hisab se andaza."""
    words = text.split()
    if not words or duration <= 0:
        return []
    weights = [len(w) + 1 for w in words]
    total = sum(weights)
    result, done = [], 0
    for word, weight in zip(words, weights):
        start = duration * done / total
        done += weight
        end = duration * done / total
        result.append(WordTiming(text=word, start=round(start, 3), end=round(end, 3)))
    return result


def pick_voice(language: str, voice: str | None = None) -> str:
    if voice:
        return voice
    name = language.strip().title()
    if name not in VOICES:
        raise ValueError(f"'{language}' ki voice set nahi. Maujood: {', '.join(VOICES)}")
    return VOICES[name]


async def edge_synthesize(text: str, voice: str, rate: str, path: Path) -> list[WordTiming]:
    """Audio file likhta hai aur word timings wapas deta hai."""
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    except TypeError:  # purani edge-tts me boundary option nahi hota
        communicate = edge_tts.Communicate(text, voice, rate=rate)
    words: list[WordTiming] = []
    with open(path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = ticks_to_seconds(chunk["offset"])
                end = round(start + ticks_to_seconds(chunk["duration"]), 3)
                words.append(WordTiming(text=chunk["text"], start=start, end=end))
    return words


def audio_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise TTSError(f"ffprobe fail: {result.stderr.strip()[-300:]}")
    return float(result.stdout.strip())


def concat_audio(paths: list[Path], out_path: Path) -> None:
    list_file = Path(out_path).with_suffix(".txt")
    lines = []
    for p in paths:
        safe = str(Path(p).resolve()).replace("\\", "/").replace("'", "'\\''")
        lines.append(f"file '{safe}'")
    list_file.write_text("\n".join(lines), encoding="utf-8")
    result = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(list_file), "-c:a", "libmp3lame", "-q:a", "2", str(out_path)],
        capture_output=True, text=True,
    )
    list_file.unlink(missing_ok=True)
    if result.returncode != 0:
        raise TTSError(f"ffmpeg audio jorne me fail: {result.stderr.strip()[-300:]}")


LEAD_PAD = 0.10   # pehle lafz se pehle itni khamoshi rakhni hai
TAIL_PAD = 0.40   # aakhri lafz ke baad itni khamoshi rakhni hai
MIN_TRIM = 0.25   # is se kam khamoshi kaatna faida nahi


def silence_trim(words: list[WordTiming], duration: float):
    """(start, length) jo awaaz ke shuru aur aakhir ki zyada khamoshi kaat de. Zarurat na ho to None."""
    start = max(0.0, words[0].start - LEAD_PAD)
    end = min(duration, words[-1].end + TAIL_PAD)
    if start + (duration - end) < MIN_TRIM:
        return None
    return round(start, 3), round(end - start, 3)


def trim_audio(path, start: float, length: float) -> None:
    path = Path(path)
    tmp = path.with_suffix(".trim.mp3")
    result = subprocess.run(
        ["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(path),
         "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-c:a", "libmp3lame", "-q:a", "2", str(tmp)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise TTSError(f"ffmpeg audio kaatne me fail: {result.stderr.strip()[-300:]}")
    tmp.replace(path)


def _synth_with_retry(synth, text, voice, rate, path, max_attempts, sleep) -> list[WordTiming]:
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return asyncio.run(synth(text, voice, rate, path))
        except Exception as exc:
            last_error = exc
            if attempt < max_attempts:
                sleep(2.0 * attempt)
    raise TTSError(f"Voiceover {max_attempts} koshish ke baad bhi fail: {last_error}") from last_error


def generate_voiceover(
    board: Storyboard,
    out_dir,
    voice: str | None = None,
    rate: str = "+0%",
    synth=edge_synthesize,
    duration_fn=audio_duration,
    concat_fn=concat_audio,
    trim_fn=trim_audio,
    max_attempts: int = 3,
    sleep=time.sleep,
) -> Voiceover:
    voice_name = pick_voice(board.language, voice)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scenes: list[SceneAudio] = []
    offset = 0.0
    for scene in board.scenes:
        path = out_dir / f"scene_{scene.number:02d}.mp3"
        words = _synth_with_retry(synth, scene.narration, voice_name, rate, path, max_attempts, sleep)
        duration = round(duration_fn(path), 3)
        if words:
            trim = silence_trim(words, duration)
            if trim:
                trim_fn(path, trim[0], trim[1])
                words = shift_words(words, -trim[0])
                duration = round(duration_fn(path), 3)
        else:
            words = fallback_word_timings(scene.narration, duration)
        scenes.append(SceneAudio(number=scene.number, path=str(path), start_offset=round(offset, 3),
                                 duration=duration, words=words))
        offset += duration

    full_path = out_dir / "voiceover.mp3"
    concat_fn([Path(s.path) for s in scenes], full_path)
    return Voiceover(path=str(full_path), voice=voice_name, duration=round(offset, 3), scenes=scenes)


def apply_durations(board: Storyboard, voiceover: Voiceover) -> Storyboard:
    """Andaze wali durations ki jagah voiceover ki asli durations lagana."""
    actual = {s.number: s.duration for s in voiceover.scenes}
    scenes = [sc.model_copy(update={"duration": actual.get(sc.number, sc.duration)}) for sc in board.scenes]
    return board.model_copy(update={"scenes": scenes})

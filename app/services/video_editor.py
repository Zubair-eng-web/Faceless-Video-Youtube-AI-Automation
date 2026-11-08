"""FFmpeg video editing: scenes, transitions, ASS captions, voiceover aur music."""
import json
import random
import shutil
import subprocess
from pathlib import Path

from app.core.config import settings
from app.core.models import Storyboard
from app.services.captions import build_ass
from app.services.fonts import caption_style
from app.services.pixabay import SceneClip
from app.services.quality import parse_black_segments
from app.services.tts import Voiceover, apply_durations

AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".ogg", ".aac")
TRANSITIONS = ("fade", "slideleft", "wipeleft", "slideright")
CAPTIONS_FILE = "captions.ass"


from app.services.audio_mix import build_audio_graph, sfx_filters
from app.services.branding import add_intro_outro, logo_overlay_filters, resolve_file
from app.services.music import mood_from_text, pick_track
from app.services.sfx import ensure_whoosh, transition_starts


class VideoError(RuntimeError):
    pass


def run_ffmpeg(args, cwd=None) -> None:
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)
    if result.returncode != 0:
        raise VideoError(f"ffmpeg fail: {result.stderr.strip()[-600:]}")


def effective_transition(durations: list[float], transition: float) -> float:
    """Transition kisi chhote scene se zyada lamba na ho."""
    if not durations:
        return 0.0
    return round(min(transition, min(durations) * 0.4), 3)


LEADING_BLACK_MAX = 2.0  # is se zyada kala ho to clip ko chhedna theek nahi (clip hi andheri ho sakti hai)


def detect_leading_black(path, runner=subprocess.run) -> float:
    """Clip ke shuru me kala screen kitni der hai (seconds). Pehle 3 second dekhta hai."""
    try:
        result = runner(
            ["ffmpeg", "-hide_banner", "-nostats", "-nostdin", "-t", "3", "-i", str(path),
             "-vf", "blackdetect=d=0.1:pix_th=0.08", "-an", "-f", "null", "-"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except OSError:
        return 0.0
    for start, end in parse_black_segments(result.stderr or ""):
        if start <= 0.05:
            return round(end, 2) if end <= LEADING_BLACK_MAX else 0.0
    return 0.0


def segment_args(clip_path, duration: float, out_path, width: int, height: int, fps: int, crf: int,
                 start: float = 0.0) -> list[str]:
    """Ek clip ko 9:16 me center-crop karke scene ki lambai tak kaatna (chhoti clip loop hoti hai)."""
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,fps={fps},format=yuv420p"
    )
    return [
        "ffmpeg", "-y", "-nostdin", "-loglevel", "error",
        "-stream_loop", "-1", *(["-ss", f"{start:.2f}"] if start > 0 else []), "-i", str(clip_path),
        "-t", f"{duration:.3f}", "-vf", vf, "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
        str(out_path),
    ]


def build_filter_complex(
    durations: list[float],
    transition: float = 0.3,
    transitions=TRANSITIONS,
    music: bool = False,
    music_volume: float = 0.12,
    fonts: bool = False,
    duck: bool = False,
    sfx_starts: list[float] | None = None,
    sfx_index: int | None = None,
    sfx_volume: float = 0.35,
    logo_index: int | None = None,
    logo_opts: dict | None = None,
    video_width: int = 1080,
) -> str:
    n = len(durations)
    if n == 0:
        raise VideoError("Koi scene nahi hai")
    total = sum(durations)
    t = effective_transition(durations, transition)

    parts: list[str] = []
    last = "[0:v]"
    offset = 0.0
    for k in range(1, n):
        offset += durations[k - 1]
        tr = transitions[(k - 1) % len(transitions)]
        label = f"[v{k}]"
        parts.append(f"{last}[{k}:v]xfade=transition={tr}:duration={t:.3f}:offset={offset:.3f}{label}")
        last = label
    ass = "ass=" + CAPTIONS_FILE + (":fontsdir=fonts" if fonts else "")
    if logo_index is not None:
        parts.append(f"{last}{ass}[vcap]")
        parts += logo_overlay_filters("vcap", logo_index, "vout", video_width, **(logo_opts or {}))
    else:
        parts.append(f"{last}{ass}[vout]")

    stereo = "aresample=44100,aformat=channel_layouts=stereo"
    voice = f"[{n}:a]"
    if music or sfx_starts:
        parts.append(f"{voice}{stereo}[voice]")
        music_label = None
        sfx_label = None
        if music:
            fade_start = max(0.0, total - 1.5)
            parts.append(
                f"[{n + 1}:a]{stereo},volume={music_volume:.3f},afade=t=out:st={fade_start:.3f}:d=1.5[music]"
            )
            music_label = "music"
        if sfx_starts:
            idx = sfx_index if sfx_index is not None else n + 1 + (1 if music else 0)
            sfx_parts, sfx_label = sfx_filters(sfx_starts, idx, sfx_volume)
            parts += sfx_parts
        parts += build_audio_graph("voice", music_label, sfx_label, duck=duck)
    else:
        parts.append(f"{voice}{stereo}[aout]")
    return ";".join(parts)


def pick_music(music_dir, rng=random) -> Path | None:
    folder = Path(music_dir)
    if not folder.is_dir():
        return None
    tracks = sorted(p for p in folder.iterdir() if p.suffix.lower() in AUDIO_EXTS)
    return rng.choice(tracks) if tracks else None


def prepare_fonts(fonts_dir, work_dir) -> bool:
    """Fonts ko video ke work folder me copy karna taake libass unhe seedha dhoond le."""
    src = Path(fonts_dir)
    fonts = [p for p in src.iterdir() if p.suffix.lower() in (".ttf", ".otf", ".ttc")] if src.is_dir() else []
    if not fonts:
        return False
    dest = Path(work_dir) / "fonts"
    dest.mkdir(parents=True, exist_ok=True)
    for f in fonts:
        shutil.copy2(f, dest / f.name)
    return True


def render_video(
    board: Storyboard,
    clips: list[SceneClip],
    voiceover: Voiceover,
    out_dir,
    music_dir=None,
    fonts_dir=None,
    transition: float = 0.3,
    music_volume: float | None = None,
    duck: bool = True,
    sfx: bool = True,
    branding=None,
    width: int | None = None,
    height: int | None = None,
    fps: int | None = None,
    crf: int = 21,
    runner=run_ffmpeg,
    rng=random,
    black_fn=detect_leading_black,
) -> Path:
    width = width or settings.video_width
    height = height or settings.video_height
    fps = fps or settings.video_fps

    board = apply_durations(board, voiceover)  # voiceover ki asli durations
    by_scene = {c.scene_number: c for c in clips}
    missing = [s.number for s in board.scenes if s.number not in by_scene]
    if missing:
        raise VideoError(f"In scenes ki clip nahi mili: {missing}")

    durations = [s.duration for s in board.scenes]
    total = round(sum(durations), 3)
    t = effective_transition(durations, transition)

    out_dir = Path(out_dir)
    seg_dir = out_dir / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)

    segments: list[Path] = []
    for i, scene in enumerate(board.scenes):
        seg = (seg_dir / f"seg_{scene.number:02d}.mp4").resolve()
        length = scene.duration + (t if i < len(board.scenes) - 1 else 0.0)
        clip_path = Path(by_scene[scene.number].path).resolve()
        start = black_fn(clip_path)
        runner(segment_args(clip_path, length, seg, width, height, fps, crf, start=start))
        if not seg.exists() or seg.stat().st_size == 0:
            raise VideoError(f"Scene {scene.number} ka segment nahi bana")
        segments.append(seg)

    style = caption_style(board.language, fonts_dir or settings.fonts_dir)
    ass_extra = {}
    if branding is not None:
        style["font_size"] = int(style["font_size"] * branding.font_scale)
        ass_extra = {"highlight_color": branding.highlight_color, "text_color": branding.text_color}
    (out_dir / CAPTIONS_FILE).write_text(build_ass(voiceover.words, width, height, **style, **ass_extra), encoding="utf-8")
    has_fonts = prepare_fonts(fonts_dir or settings.fonts_dir, out_dir)
    mdir = music_dir or settings.music_dir
    mood = mood_from_text(" ".join([board.title, board.hook, board.full_narration]))
    music = pick_track(mdir, mood, rng)
    if music_volume is None:
        music_volume = 0.25 if duck else 0.12
    whoosh = ensure_whoosh(Path(settings.music_dir).parent / "cache" / "sfx") if sfx else None
    sfx_starts = transition_starts(durations, t) if whoosh is not None else []
    sfx_index = len(board.scenes) + 1 + (1 if music is not None else 0)
    brand_dir = Path(settings.music_dir).parent / "branding"
    logo = resolve_file(branding.logo_path, brand_dir) if branding is not None else None
    logo_index = (len(board.scenes) + 1 + (1 if music is not None else 0) + (1 if sfx_starts else 0)
                  if logo is not None else None)
    logo_opts = ({"position": branding.logo_position, "opacity": branding.logo_opacity,
                  "width_frac": branding.logo_width} if logo is not None else None)
    fc = build_filter_complex(durations, transition, music=music is not None,
                              music_volume=music_volume, fonts=has_fonts,
                              duck=duck, sfx_starts=sfx_starts, sfx_index=sfx_index,
                              logo_index=logo_index, logo_opts=logo_opts, video_width=width)

    out_path = (out_dir / "video.mp4").resolve()
    cmd = ["ffmpeg", "-y", "-nostdin", "-loglevel", "error"]
    for seg in segments:
        cmd += ["-i", str(seg)]
    cmd += ["-i", str(Path(voiceover.path).resolve())]
    if music is not None:
        cmd += ["-stream_loop", "-1", "-i", str(Path(music).resolve())]
    if sfx_starts:
        cmd += ["-i", str(Path(whoosh).resolve())]
    if logo is not None:
        cmd += ["-i", str(logo)]
    cmd += [
        "-filter_complex", fc, "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        "-t", f"{total:.3f}", str(out_path),
    ]
    runner(cmd, cwd=out_dir)
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise VideoError("Final video file nahi bani")
    if branding is not None:
        intro = resolve_file(branding.intro_path, brand_dir)
        outro = resolve_file(branding.outro_path, brand_dir)
        if intro or outro:
            out_path = add_intro_outro(out_path, intro, outro, out_dir, width, height, fps)
    return out_path


def probe_video(path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise VideoError(f"ffprobe fail: {result.stderr.strip()[-300:]}")
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    return {"width": stream["width"], "height": stream["height"], "duration": float(data["format"]["duration"])}

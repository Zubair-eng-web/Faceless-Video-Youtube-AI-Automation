"""Channel branding: caption ke rang aur font ka size, logo watermark, intro/outro ke raste."""
import json
import re
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")
POSITIONS = ("top-left", "top-right", "bottom-left", "bottom-right", "center")


def normalize_hex(value: str) -> str:
    m = HEX_RE.match((value or "").strip())
    if not m:
        raise ValueError(f"Rang galat hai: {value!r} (maslan #FFFF00)")
    return "#" + m.group(1).upper()


def ass_bgr(hex_color: str) -> str:
    h = normalize_hex(hex_color)[1:]
    return h[4:6] + h[2:4] + h[0:2]  # ASS mein rang BGR order mein hota hai


def ass_style_color(hex_color: str) -> str:
    """ASS Style line ke liye, maslan &H0000FFFF."""
    return f"&H00{ass_bgr(hex_color)}"


def ass_tag_color(hex_color: str) -> str:
    """Text ke andar rang badalne ka tag, maslan {\\c&H00FFFF&}."""
    return "{\\c&H" + ass_bgr(hex_color) + "&}"


class Branding(BaseModel):
    highlight_color: str = "#FFFF00"
    text_color: str = "#FFFFFF"
    font_scale: float = Field(1.0, ge=0.6, le=1.6)
    logo_path: str | None = None
    logo_position: str = "top-right"
    logo_opacity: float = Field(0.8, ge=0.1, le=1.0)
    logo_width: float = Field(0.18, ge=0.05, le=0.4)  # video ki chaurai ka hissa
    intro_path: str | None = None
    outro_path: str | None = None

    @field_validator("highlight_color", "text_color")
    @classmethod
    def _color(cls, v):
        return normalize_hex(v)

    @field_validator("logo_position")
    @classmethod
    def _position(cls, v):
        if v not in POSITIONS:
            raise ValueError(f"Position in mein se ho: {', '.join(POSITIONS)}")
        return v


def resolve_file(path, base_dir=None) -> Path | None:
    """File mil jaye to uska poora path, warna None (branding adhoori ho to video na rukey)."""
    if not path:
        return None
    p = Path(path)
    if not p.is_absolute() and base_dir:
        p = Path(base_dir) / p
    return p.resolve() if p.is_file() else None


def _xy(position: str, margin: int) -> str:
    return {
        "top-left": f"{margin}:{margin}",
        "top-right": f"W-w-{margin}:{margin}",
        "bottom-left": f"{margin}:H-h-{margin}",
        "bottom-right": f"W-w-{margin}:H-h-{margin}",
        "center": "(W-w)/2:(H-h)/2",
    }[position]


def logo_overlay_filters(video: str, logo_index: int, out: str, video_width: int,
                         position: str = "top-right", opacity: float = 0.8,
                         width_frac: float = 0.18, margin: int = 40) -> list[str]:
    """Labels bina [ ] ke dein. video label par logo laga kar out label banata hai."""
    w = max(int(video_width * width_frac), 16)
    return [
        f"[{logo_index}:v]scale={w}:-1,format=rgba,colorchannelmixer=aa={opacity:.2f}[logo]",
        f"[{video}][logo]overlay={_xy(position, margin)}[{out}]",
    ]


def branding_from_row(row):
    """Channel ki row se Branding. Settings na hon ya kharab hon to None (purana look)."""
    raw = (row or {}).get("branding_json")
    if not raw:
        return None
    try:
        return Branding.model_validate(json.loads(raw))
    except (ValueError, TypeError):
        return None


def probe_clip(path, runner=subprocess.run):
    """(duration, has_audio) ffprobe se."""
    r = runner(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                "-of", "json", str(path)], capture_output=True, text=True)
    data = json.loads(r.stdout or "{}")
    dur = float((data.get("format") or {}).get("duration") or 0)
    has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
    return dur, has_audio


def build_concat_graph(infos, width: int, height: int, fps: int) -> str:
    """infos: [(duration, has_audio), ...]. Sab clips ek size par la kar jorta hai."""
    parts, labels = [], ""
    afmt = "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo"
    for i, (dur, has_audio) in enumerate(infos):
        parts.append(f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                     f"crop={width}:{height},setsar=1,fps={fps},format=yuv420p[v{i}]")
        if has_audio:
            parts.append(f"[{i}:a]aresample=44100,{afmt}[a{i}]")
        else:
            parts.append(f"anullsrc=r=44100:cl=stereo,atrim=duration={dur:.3f},{afmt}[a{i}]")
        labels += f"[v{i}][a{i}]"
    parts.append(f"{labels}concat=n={len(infos)}:v=1:a=1[vout][aout]")
    return ";".join(parts)


def add_intro_outro(video, intro, outro, out_dir, width, height, fps,
                    runner=subprocess.run, probe=probe_clip):
    """Intro/outro jorta hai. Kuch bhi fail ho to asli video wapas (video nahi rukti)."""
    video = Path(video)
    clips = [Path(f) for f in (intro, video, outro) if f]
    if len(clips) == 1:
        return video
    out_dir = Path(out_dir)
    branded = out_dir / "video_branded.mp4"
    try:
        infos = [probe(f) for f in clips]
        cmd = ["ffmpeg", "-y", "-nostdin", "-loglevel", "error"]
        for f in clips:
            cmd += ["-i", str(f)]
        cmd += ["-filter_complex", build_concat_graph(infos, width, height, fps),
                "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", str(branded)]
        r = runner(cmd, capture_output=True, text=True)
    except (OSError, ValueError):
        return video
    if getattr(r, "returncode", 1) != 0 or not branded.exists() or branded.stat().st_size == 0:
        return video
    video.replace(out_dir / "video_core.mp4")
    branded.replace(video)
    return video

import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
files = {}


def edit(rel, pairs):
    t = files.get(rel) or (root / rel).read_text(encoding="utf-8")
    for old, new in pairs:
        n = t.count(old)
        if n != 1:
            print(f"[FAIL] {rel}: pattern {n} dafa mila: {old[:70]!r}. Kuch nahi badla.")
            raise SystemExit(1)
        t = t.replace(old, new)
    files[rel] = t


if "branding" in (root / "app/services/video_editor.py").read_text(encoding="utf-8"):
    print("Pehle se patch ho chuka hai")
    raise SystemExit(0)

EXTRA = '''

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
'''

edit("app/services/branding.py", [("import re\nfrom pathlib import Path\n",
                                   "import json\nimport re\nimport subprocess\nfrom pathlib import Path\n")])
files["app/services/branding.py"] += EXTRA

edit("app/services/captions.py", [
    ("SENTENCE_END = (", "from app.services.branding import ass_style_color, ass_tag_color\n\nSENTENCE_END = ("),
    ("    uppercase: bool = True,\n) -> str:\n    lines = [",
     "    uppercase: bool = True,\n    highlight_color: str | None = None,\n    text_color: str | None = None,\n) -> str:\n"
     "    hl_on = ass_tag_color(highlight_color) if highlight_color else HL_ON\n"
     "    hl_off = ass_tag_color(text_color) if text_color else HL_OFF\n"
     '    primary = ass_style_color(text_color) if text_color else "&H00FFFFFF"\n'
     "    lines = ["),
    ("{font_size},&H00FFFFFF,&H00FFFFFF,", "{font_size},{primary},{primary},"),
    ("HL_ON + t + HL_OFF", "hl_on + t + hl_off"),
])

edit("app/services/video_editor.py", [
    ("from app.services.audio_mix import build_audio_graph, sfx_filters\n",
     "from app.services.audio_mix import build_audio_graph, sfx_filters\n"
     "from app.services.branding import add_intro_outro, logo_overlay_filters, resolve_file\n"),
    ("    sfx_volume: float = 0.35,\n) -> str:",
     "    sfx_volume: float = 0.35,\n    logo_index: int | None = None,\n    logo_opts: dict | None = None,\n"
     "    video_width: int = 1080,\n) -> str:"),
    ('    parts.append(f"{last}{ass}[vout]")\n',
     '    if logo_index is not None:\n'
     '        parts.append(f"{last}{ass}[vcap]")\n'
     '        parts += logo_overlay_filters("vcap", logo_index, "vout", video_width, **(logo_opts or {}))\n'
     '    else:\n'
     '        parts.append(f"{last}{ass}[vout]")\n'),
    ("    sfx: bool = True,\n    width: int | None = None,",
     "    sfx: bool = True,\n    branding=None,\n    width: int | None = None,"),
    ("    style = caption_style(board.language, fonts_dir or settings.fonts_dir)\n",
     "    style = caption_style(board.language, fonts_dir or settings.fonts_dir)\n"
     "    ass_extra = {}\n"
     "    if branding is not None:\n"
     '        style["font_size"] = int(style["font_size"] * branding.font_scale)\n'
     '        ass_extra = {"highlight_color": branding.highlight_color, "text_color": branding.text_color}\n'),
    ("build_ass(voiceover.words, width, height, **style)",
     "build_ass(voiceover.words, width, height, **style, **ass_extra)"),
    ("    fc = build_filter_complex(durations, transition, music=music is not None,\n"
     "                              music_volume=music_volume, fonts=has_fonts,\n"
     "                              duck=duck, sfx_starts=sfx_starts, sfx_index=sfx_index)\n",
     "    brand_dir = Path(settings.music_dir).parent / \"branding\"\n"
     "    logo = resolve_file(branding.logo_path, brand_dir) if branding is not None else None\n"
     "    logo_index = (len(board.scenes) + 1 + (1 if music is not None else 0) + (1 if sfx_starts else 0)\n"
     "                  if logo is not None else None)\n"
     "    logo_opts = ({\"position\": branding.logo_position, \"opacity\": branding.logo_opacity,\n"
     "                  \"width_frac\": branding.logo_width} if logo is not None else None)\n"
     "    fc = build_filter_complex(durations, transition, music=music is not None,\n"
     "                              music_volume=music_volume, fonts=has_fonts,\n"
     "                              duck=duck, sfx_starts=sfx_starts, sfx_index=sfx_index,\n"
     "                              logo_index=logo_index, logo_opts=logo_opts, video_width=width)\n"),
    ('    if sfx_starts:\n        cmd += ["-i", str(Path(whoosh).resolve())]\n',
     '    if sfx_starts:\n        cmd += ["-i", str(Path(whoosh).resolve())]\n'
     '    if logo is not None:\n        cmd += ["-i", str(logo)]\n'),
    ('        raise VideoError("Final video file nahi bani")\n    return out_path\n',
     '        raise VideoError("Final video file nahi bani")\n'
     '    if branding is not None:\n'
     '        intro = resolve_file(branding.intro_path, brand_dir)\n'
     '        outro = resolve_file(branding.outro_path, brand_dir)\n'
     '        if intro or outro:\n'
     '            out_path = add_intro_outro(out_path, intro, outro, out_dir, width, height, fps)\n'
     '    return out_path\n'),
])

edit("app/pipeline.py", [
    ("    fact_fn=run_fact_check,\n) -> PipelineResult:",
     "    fact_fn=run_fact_check,\n    branding=None,\n) -> PipelineResult:"),
    ('_step("render", render_fn, board, clips, vo, run_dir)',
     '_step("render", render_fn, board, clips, vo, run_dir,\n                 **({"branding": branding} if branding else {}))'),
])

edit("app/api/runner.py", [
    ("def default_runner(topic, niche, language, seconds, voice, used_topics) -> PipelineResult:",
     "def default_runner(topic, niche, language, seconds, voice, used_topics, branding=None) -> PipelineResult:"),
    ("language=language, target_seconds=seconds, voice=voice,",
     'language=language, target_seconds=seconds, voice=voice,\n            **({"branding": branding} if branding else {}),'),
])

edit("app/api/main.py", [
    ("from app.api.schemas import ChannelCreate, GenerateRequest\n",
     "from app.api.schemas import ChannelCreate, GenerateRequest\n"
     "from app.services.branding import Branding, branding_from_row\n"),
    ("def run_job(video_id, channel_id, topic, niche, language, seconds, voice):",
     "def run_job(video_id, channel_id, topic, niche, language, seconds, voice, branding=None):"),
    ("voice=voice, used_topics=used)",
     'voice=voice, used_topics=used, **({"branding": branding} if branding else {}))'),
    ("background.add_task(run_job, video_id, body.channel_id, topic, niche, language, body.seconds, voice)",
     "background.add_task(run_job, video_id, body.channel_id, topic, niche, language, body.seconds, voice,\n"
     "                            branding_from_row(channel) if channel else None)"),
    ('    @app.delete("/channels/{channel_id}")\n',
     '    @app.get("/channels/{channel_id}/branding")\n'
     '    def get_branding(channel_id: int):\n'
     '        channel = db.get_channel(path, channel_id)\n'
     '        if channel is None:\n'
     '            raise HTTPException(404, "Channel nahi mila")\n'
     '        return (branding_from_row(channel) or Branding()).model_dump()\n\n'
     '    @app.put("/channels/{channel_id}/branding")\n'
     '    def put_branding(channel_id: int, body: Branding):\n'
     '        if not db.set_channel_branding(path, channel_id, body.model_dump_json()):\n'
     '            raise HTTPException(404, "Channel nahi mila")\n'
     '        return body.model_dump()\n\n'
     '    @app.delete("/channels/{channel_id}")\n'),
])

edit("app/core/db.py", [
    ("    ALTER TABLE channels ADD COLUMN video_seconds INTEGER NOT NULL DEFAULT 40;\n    \"\"\",\n]",
     "    ALTER TABLE channels ADD COLUMN video_seconds INTEGER NOT NULL DEFAULT 40;\n    \"\"\",\n"
     "    \"\"\"\n    ALTER TABLE channels ADD COLUMN branding_json TEXT;\n    \"\"\",\n]"),
])
files["app/core/db.py"] = files["app/core/db.py"].rstrip("\n") + '''


def set_channel_branding(db_path, channel_id: int, branding_json) -> bool:
    """Channel ki branding settings (JSON) likhna. None dene se branding hat jati hai."""
    with connect(db_path) as con:
        return con.execute("UPDATE channels SET branding_json = ? WHERE id = ?",
                           (branding_json, channel_id)).rowcount > 0
'''

bak = root / "output" / "step17_bak"
bak.mkdir(parents=True, exist_ok=True)
for rel in files:
    src = root / rel
    shutil.copy(src, bak / rel.replace("/", "__"))
for rel, text in files.items():
    (root / rel).write_text(text, encoding="utf-8")

r = root / "README.md"
t = r.read_text(encoding="utf-8")
t = t.replace("Total 368 tests", "Total 367 tests").replace("Step 16 par 368 tests", "Step 16 par 367 tests")
r.write_text(t, encoding="utf-8")
print("[OK] 6 files patch ho gayin. Backups: output/step17_bak")

"""Long-form 16:9 render: chunk-wise video, resume, merge, final audio mix."""
import hashlib
import json
import os
import random
import time
from pathlib import Path

from app.core.config import settings
from app.services.audio_mix import build_audio_graph, sfx_filters
from app.services.captions import build_ass
from app.services.fonts import caption_style
from app.services.music import mood_from_text, pick_track
from app.services.sfx import ensure_whoosh
from app.services.tts import apply_durations
from app.services.video_editor import (TRANSITIONS, VideoError, detect_leading_black, effective_transition,
                                       prepare_fonts, probe_video, run_ffmpeg, segment_args)

MAX_CHUNK_SCENES = 20
CAPTION_SCALE = 0.7  # landscape par vertical wali font bohat bari hoti hai
STEREO = "aresample=44100,aformat=channel_layouts=stereo"


def plan_chunks(n: int, chapter_ends, max_scenes: int = MAX_CHUNK_SCENES) -> list[tuple[int, int]]:
    """Scene indexes [a, b) ke chunks. Chapter ki hadd par kategte hain; bara chapter barabar hisson mein."""
    if n <= 0:
        return []
    ends = sorted({e for e in chapter_ends if 0 < e < n}) + [n]
    chunks, start = [], 0
    for end in ends:
        count = end - start
        parts = -(-count // max_scenes)
        size = -(-count // parts)
        for a in range(start, end, size):
            chunks.append((a, min(a + size, end)))
        start = end
    return chunks


def chunk_words(words, t0: float, t1: float) -> list:
    """Global word timings me se [t0, t1) wale, chunk ke waqt ke hisab se shifted."""
    out = []
    for w in words:
        if t0 <= w.start < t1:
            out.append(w.model_copy(update={"start": round(w.start - t0, 3),
                                            "end": round(min(w.end, t1) - t0, 3)}))
    return out


def chunk_filter(durations: list[float], t: float, fonts: bool, ass_name: str) -> str:
    parts, last, offset = [], "[0:v]", 0.0
    for k in range(1, len(durations)):
        offset += durations[k - 1]
        tr = TRANSITIONS[(k - 1) % len(TRANSITIONS)]
        parts.append(f"{last}[{k}:v]xfade=transition={tr}:duration={t:.3f}:offset={offset:.3f}[v{k}]")
        last = f"[v{k}]"
    parts.append(f"{last}ass={ass_name}{':fontsdir=fonts' if fonts else ''}[vout]")
    return ";".join(parts)


def chunk_signature(scenes, by_scene, width, height, fps, t) -> str:
    raw = json.dumps([[s.number, round(s.duration, 2), by_scene[s.number].clip_id, s.narration] for s in scenes]
                     + [width, height, fps, t], ensure_ascii=False)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def render_long_video(board, clips, voiceover, out_dir, chapter_ends=(), fonts_dir=None, music_dir=None,
                      transition: float = 0.4, duck: bool = True, sfx: bool = True, width=None, height=None,
                      fps=None, crf: int = 21, max_chunk_scenes: int = MAX_CHUNK_SCENES,
                      runner=run_ffmpeg, black_fn=detect_leading_black, rng=random, progress=print) -> Path:
    width = width or getattr(settings, "long_video_width", 1920)
    height = height or getattr(settings, "long_video_height", 1080)
    fps = fps or settings.video_fps

    board = apply_durations(board, voiceover)
    by_scene = {c.scene_number: c for c in clips}
    missing = [s.number for s in board.scenes if s.number not in by_scene]
    if missing:
        raise VideoError(f"In scenes ki clip nahi mili: {missing}")

    scenes = board.scenes
    durations = [s.duration for s in scenes]
    t = effective_transition(durations, transition)
    total = round(sum(durations), 3)
    starts, acc = [], 0.0
    for d in durations:
        starts.append(acc)
        acc += d

    out = Path(out_dir)
    chunk_dir, work = out / "chunks", out / "work"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    fonts_src = fonts_dir or settings.fonts_dir
    has_fonts = prepare_fonts(fonts_src, work)
    style = caption_style(board.language, fonts_src)
    style["font_size"] = int(style["font_size"] * CAPTION_SCALE)

    began = time.time()
    plan = plan_chunks(len(scenes), chapter_ends, max_chunk_scenes)
    files, rendered = [], 0
    for ci, (a, b) in enumerate(plan, 1):
        sub = scenes[a:b]
        final = chunk_dir / f"chunk_{ci:03d}.mp4"
        sigf = final.with_suffix(".sig")
        sig = chunk_signature(sub, by_scene, width, height, fps, t)
        if final.exists() and final.stat().st_size > 0 and sigf.exists() and sigf.read_text() == sig:
            progress(f"Chunk {ci}/{len(plan)} pehle se tayyar (skip)")
            files.append(final)
            continue
        final.unlink(missing_ok=True)
        progress(f"Chunk {ci}/{len(plan)}: scenes {sub[0].number}-{sub[-1].number}")
        segs = []
        for i, sc in enumerate(sub):
            seg = (chunk_dir / f"seg_{sc.number:03d}.mp4").resolve()
            length = sc.duration + (t if i < len(sub) - 1 else 0.0)
            clip_path = Path(by_scene[sc.number].path).resolve()
            runner(segment_args(clip_path, length, seg, width, height, fps, crf, start=black_fn(clip_path)))
            if not seg.exists() or seg.stat().st_size == 0:
                raise VideoError(f"Scene {sc.number} ka segment nahi bana")
            segs.append(seg)
        t0 = starts[a]
        t1 = starts[b - 1] + durations[b - 1]
        ass_name = f"cap_{ci:03d}.ass"
        (work / ass_name).write_text(build_ass(chunk_words(voiceover.words, t0, t1), width, height, **style),
                                     encoding="utf-8")
        tmp = (chunk_dir / f"chunk_{ci:03d}.tmp.mp4").resolve()
        cmd = ["ffmpeg", "-y", "-nostdin", "-loglevel", "error"]
        for s in segs:
            cmd += ["-i", str(s)]
        cmd += ["-filter_complex", chunk_filter([x.duration for x in sub], t, has_fonts, ass_name),
                "-map", "[vout]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
                "-pix_fmt", "yuv420p", "-r", str(fps), "-t", f"{t1 - t0:.3f}", str(tmp)]
        runner(cmd, cwd=work)
        if not tmp.exists() or tmp.stat().st_size == 0:
            raise VideoError(f"Chunk {ci} nahi bana")
        os.replace(tmp, final)
        sigf.write_text(sig)
        for s in segs:
            s.unlink(missing_ok=True)
        files.append(final)
        rendered += 1

    (chunk_dir / "concat.txt").write_text("".join(f"file '{f.name}'\n" for f in files), encoding="utf-8")
    merged = (chunk_dir / "merged.mp4").resolve()
    runner(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-f", "concat", "-safe", "0",
            "-i", "concat.txt", "-c", "copy", str(merged)], cwd=chunk_dir)

    mdir = music_dir or settings.music_dir
    music = pick_track(mdir, mood_from_text(" ".join([board.title, board.hook])), rng)
    whoosh = ensure_whoosh(Path(settings.music_dir).parent / "cache" / "sfx") if sfx else None
    bounds = sorted({e for e in chapter_ends if 0 < e < len(scenes)})
    sfx_starts = [round(max(0.0, starts[e] - 0.1), 3) for e in bounds] if whoosh is not None else []

    cmd = ["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(merged),
           "-i", str(Path(voiceover.path).resolve())]
    idx, music_label, sfx_label = 2, None, None
    parts = [f"[1:a]{STEREO}[voice]"]
    if music is not None:
        vol = 0.25 if duck else 0.12
        cmd += ["-stream_loop", "-1", "-i", str(Path(music).resolve())]
        parts.append(f"[{idx}:a]{STEREO},volume={vol:.3f},afade=t=out:st={max(0.0, total - 3):.3f}:d=3[music]")
        music_label, idx = "music", idx + 1
    if sfx_starts:
        cmd += ["-i", str(Path(whoosh).resolve())]
        sfx_parts, sfx_label = sfx_filters(sfx_starts, idx, 0.3)
        parts += sfx_parts
    if music_label or sfx_label:
        parts += build_audio_graph("voice", music_label, sfx_label, duck=duck)
    else:
        parts = [f"[1:a]{STEREO}[aout]"]
    out_path = (out / "video.mp4").resolve()
    cmd += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[aout]", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{total:.3f}", str(out_path)]
    runner(cmd)
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise VideoError("Final video file nahi bani")

    info = probe_video(out_path)
    if (info["width"], info["height"]) != (width, height):
        raise VideoError(f"Video size {info['width']}x{info['height']} aayi, {width}x{height} chahiye thi")
    report = {"width": width, "height": height, "chunks": len(plan), "chunks_rendered_now": rendered,
              "expected_seconds": total, "actual_seconds": round(info["duration"], 2),
              "drift_seconds": round(info["duration"] - total, 2), "music": str(music) if music else None,
              "whoosh_count": len(sfx_starts), "render_seconds": round(time.time() - began, 1)}
    (out / "render_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    progress(f"Render complete: {report}")
    return out_path

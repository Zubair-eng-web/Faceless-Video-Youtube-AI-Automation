import re, shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
p = root / "app" / "services" / "video_editor.py"
t = p.read_text(encoding="utf-8")

if "build_audio_graph" in t:
    print("Pehle se patch ho chuka hai")
    raise SystemExit(0)

(root / "output").mkdir(exist_ok=True)
shutil.copy(p, root / "output" / "video_editor.bak")


def sub(text, pattern, repl, flags=0):
    new, n = re.subn(pattern, lambda m: repl, text, flags=flags)
    if n != 1:
        print(f"[FAIL] pattern ek dafa nahi mila ({n}): {pattern[:60]}")
        print("Kuch nahi badla. Backup: output/video_editor.bak")
        raise SystemExit(1)
    return new


t = sub(t, r"class VideoError\(RuntimeError\):",
        "from app.services.audio_mix import build_audio_graph, sfx_filters\n"
        "from app.services.music import mood_from_text, pick_track\n"
        "from app.services.sfx import ensure_whoosh, transition_starts\n\n\n"
        "class VideoError(RuntimeError):")

t = sub(t, r"    music_volume: float = 0\.12,\n    fonts: bool = False,\n\) -> str:",
        "    music_volume: float = 0.12,\n    fonts: bool = False,\n"
        "    duck: bool = False,\n    sfx_starts: list[float] | None = None,\n"
        "    sfx_index: int | None = None,\n    sfx_volume: float = 0.35,\n) -> str:")

new_audio = '''    stereo = "aresample=44100,aformat=channel_layouts=stereo"
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
'''
t = sub(t, r'    stereo = "aresample=44100,aformat=channel_layouts=stereo"\n.*?    return ";"\.join\(parts\)\n',
        new_audio, flags=re.S)

t = sub(t, r"    music_volume: float = 0\.12,\n    width: int \| None = None,",
        "    music_volume: float | None = None,\n    duck: bool = True,\n    sfx: bool = True,\n"
        "    width: int | None = None,")

new_pick = '''    mdir = music_dir or settings.music_dir
    mood = mood_from_text(" ".join([board.title, board.hook, board.full_narration]))
    music = pick_track(mdir, mood, rng)
    if music_volume is None:
        music_volume = 0.25 if duck else 0.12
    whoosh = ensure_whoosh(Path(settings.music_dir).parent / "cache" / "sfx") if sfx else None
    sfx_starts = transition_starts(durations, t) if whoosh is not None else []
    sfx_index = len(board.scenes) + 1 + (1 if music is not None else 0)
    fc = build_filter_complex(durations, transition, music=music is not None,
                              music_volume=music_volume, fonts=has_fonts,
                              duck=duck, sfx_starts=sfx_starts, sfx_index=sfx_index)
'''
t = sub(t, r"    music = pick_music\(.*?fonts=has_fonts\)\n", new_pick, flags=re.S)

t = sub(t, r'(    if music is not None:\n        cmd \+= \["-stream_loop", "-1", "-i", str\(Path\(music\)\.resolve\(\)\)\]\n)',
        '    if music is not None:\n        cmd += ["-stream_loop", "-1", "-i", str(Path(music).resolve())]\n'
        '    if sfx_starts:\n        cmd += ["-i", str(Path(whoosh).resolve())]\n')

p.write_text(t, encoding="utf-8")
print("[OK] video_editor.py patch ho gayi")

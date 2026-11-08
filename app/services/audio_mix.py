"""Audio filter graph: voiceover, music (ducking ke saath) aur sound effects ka mix.

Saare labels bina [ ] ke dein, maslan "voice". Output label "aout" hota hai.
"""

FMT = "aformat=sample_rates=44100:channel_layouts=stereo"


def sfx_filters(starts: list[float], sfx_index: int, volume: float = 0.35, out_label: str = "sfx"):
    n = len(starts)
    if n == 0:
        return [], None
    if n == 1:
        ms = int(starts[0] * 1000)
        return [f"[{sfx_index}:a]{FMT},adelay={ms}|{ms},volume={volume:.3f}[{out_label}]"], out_label
    split = "".join(f"[sx{i}]" for i in range(n))
    parts = [f"[{sfx_index}:a]{FMT},asplit={n}{split}"]
    for i, s in enumerate(starts):
        ms = int(s * 1000)
        parts.append(f"[sx{i}]adelay={ms}|{ms}[sd{i}]")
    ins = "".join(f"[sd{i}]" for i in range(n))
    parts.append(f"{ins}amix=inputs={n}:duration=longest:dropout_transition=0,volume={n * volume:.3f}[{out_label}]")
    return parts, out_label


def build_audio_graph(voice: str, music: str | None = None, sfx: str | None = None,
                      duck: bool = True, out: str = "aout") -> list[str]:
    parts: list[str] = []
    v, m = voice, music
    if music and duck:
        parts.append(f"[{voice}]asplit=2[vmain][vkey]")
        parts.append(f"[{music}][vkey]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=400[mduck]")
        v, m = "vmain", "mduck"
    ins = [v] + ([m] if m else []) + ([sfx] if sfx else [])
    if len(ins) == 1:
        parts.append(f"[{v}]alimiter=limit=0.95[{out}]")
    else:
        joined = "".join(f"[{i}]" for i in ins)
        parts.append(f"{joined}amix=inputs={len(ins)}:duration=first:dropout_transition=0,"
                     f"volume={len(ins)},alimiter=limit=0.95[{out}]")
    return parts

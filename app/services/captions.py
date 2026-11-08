"""ASS captions: word-by-word highlight (jo lafz abhi bola ja raha hai wo peela hota hai)."""
from app.services.tts import WordTiming

from app.services.branding import ass_style_color, ass_tag_color

SENTENCE_END = (".", "!", "?", "\u06d4", "\u061f", "\u0964", "\u0965")
HL_ON = "{\\c&H00FFFF&}"   # peela (BGR order)
HL_OFF = "{\\c&HFFFFFF&}"  # safed


def fmt_time(seconds: float) -> str:
    cs = max(0, round(seconds * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def group_words(words: list[WordTiming], max_words: int = 3, max_chars: int = 18) -> list[list[WordTiming]]:
    """Lafzon ke chhote groups: har screen par 1 se 3 lafz."""
    groups: list[list[WordTiming]] = []
    cur: list[WordTiming] = []
    for w in words:
        text = w.text.strip()
        if not text:
            continue
        cur_chars = sum(len(x.text.strip()) for x in cur) + len(cur)
        if cur and (len(cur) >= max_words or cur_chars + len(text) > max_chars):
            groups.append(cur)
            cur = []
        cur.append(w)
        if text.endswith(SENTENCE_END):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def _esc(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\\", "").replace("\n", " ").strip()


def build_ass(
    words: list[WordTiming],
    width: int = 1080,
    height: int = 1920,
    font: str = "Arial",
    font_size: int = 78,
    margin_v: int = 480,
    max_words: int = 3,
    max_chars: int = 18,
    uppercase: bool = True,
    highlight_color: str | None = None,
    text_color: str | None = None,
) -> str:
    hl_on = ass_tag_color(highlight_color) if highlight_color else HL_ON
    hl_off = ass_tag_color(text_color) if text_color else HL_OFF
    primary = ass_style_color(text_color) if text_color else "&H00FFFFFF"
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font},{font_size},{primary},{primary},&H00000000,&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,7,2,2,60,60,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for group in group_words(words, max_words, max_chars):
        texts = [_esc(w.text.upper() if uppercase else w.text) for w in group]
        for i, w in enumerate(group):
            start = w.start
            end = group[i + 1].start if i + 1 < len(group) else w.end
            end = max(end, start + 0.05)
            shown = [hl_on + t + hl_off if j == i else t for j, t in enumerate(texts)]
            text = " ".join(shown)
            lines.append(f"Dialogue: 0,{fmt_time(start)},{fmt_time(end)},Default,,0,0,0,,{text}")
    return "\n".join(lines) + "\n"

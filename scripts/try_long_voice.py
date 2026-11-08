"""Live test: long script ki narration (Edge TTS, key nahi chahiye). Pehle 10 scenes (jaldi).
Usage: python -m scripts.try_long_voice [--scenes 10] [--voice en-US-GuyNeural] [run folder]
Poori script ke liye --scenes 0. Dobara chalane par bane hue scenes skip hote hain.
Text badla ho to run folder ka narration folder delete kar dein."""
import argparse
from pathlib import Path

from app.services.long_narration import NarrationConfig, generate_long_voiceover
from app.services.long_script import LongScript

root = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("run", nargs="?", default=str(root / "output" / "long_test" / "how_black_holes_form_5min"))
ap.add_argument("--scenes", type=int, default=10)
ap.add_argument("--voice", default=None)
a = ap.parse_args()
run = Path(a.run)
f = run / "long_script.json"
if not f.exists():
    raise SystemExit(f"[FAIL] {f} nahi mili. Pehle: python -m scripts.try_long_script ...")
script = LongScript.model_validate_json(f.read_text(encoding="utf-8"))
cfg = NarrationConfig.from_env()
if a.voice:
    cfg.voice = a.voice
vo, rep = generate_long_voiceover(script, run / "narration", cfg=cfg, max_scenes=a.scenes or None)
print(f"\nVoice   : {vo.voice} (rate {cfg.rate})")
print("Report  :", rep.summary())
for w in rep.warnings:
    print("  [NARRATION]", w)
print("Pehle 5 scenes:")
for s in vo.scenes[:5]:
    print(f"  scene {s.number:3}: starts {s.start_offset:6.2f}s, {s.duration:5.2f}s, {len(s.words)} words")
print("Audio   :", vo.path)
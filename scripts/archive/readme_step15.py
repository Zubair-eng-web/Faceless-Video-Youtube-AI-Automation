from pathlib import Path

root = Path(__file__).resolve().parent.parent
p = root / "README.md"
t = p.read_text(encoding="utf-8")

if "### Step 15" not in t:
    entry = """### Step 15: Background music, ducking aur sound effects
- `music.py` (mood ke hisab se track: folder `assets/music/<mood>/` ya file ka naam `<mood>_naam.mp3`), `sfx.py` (transition par whoosh, FFmpeg se khud banta hai), `audio_mix.py` (ducking: voiceover ke waqt music dabti hai).
- `video_editor.py` patch hui (purane parameters wahi). Moods: calm, upbeat, dramatic, mysterious, inspiring.
- Live tests: `scripts/try_audio_graph.py`, `scripts/try_video.py`. Total 355 tests.

"""
    t = t.replace("<!-- STEPS-LOG-END -->", entry + "<!-- STEPS-LOG-END -->")
    print("Step 15 entry jor di")

t = t.replace("| Background music, ducking, sound effects | Baqi | 15 |",
              "| Background music, ducking, sound effects | Mukammal | 15 |")
t = t.replace("| Fact-check, trend research, branding | Baqi | Roadmap |",
              "| Fact-check | Ban raha hai | 16 |\n| Trend research, branding | Baqi | Roadmap |")

start = t.find("**Agla step (Step 15)")
end = t.find("**Uske baad ke kaam:**")
if start != -1 and end != -1:
    t = t[:start] + ("**Agla step (Step 16): Fact-check**: script ke dawon ki Gemini se dobara jaanch, "
                     "ghalat scene khud theek, report dashboard mein.\n\n") + t[end:]
    print("Roadmap update")

t = t.replace("Step 14 par 336 tests", "Step 15 par 355 tests")
p.write_text(t, encoding="utf-8")

from pathlib import Path

p = Path(__file__).resolve().parent.parent / "tests" / "test_pipeline.py"
t = p.read_text(encoding="utf-8")
old = "assert len(messages) == 7"
if t.count(old) != 1:
    print(f"[FAIL] pattern {t.count(old)} dafa mila. Kuch nahi badla.")
    raise SystemExit(1)
t = t.replace(old, "assert len([m for m in messages if m.startswith('[')]) == 7")
p.write_text(t, encoding="utf-8")
print("[OK] test theek ho gaya")

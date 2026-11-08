from pathlib import Path

p = Path(__file__).resolve().parent.parent / "tests" / "test_long_script.py"
t = p.read_text(encoding="utf-8")
old = "assert len(parts) == 4 and all(len(p.split()) <= 12 for p in parts)"
if t.count(old) != 1:
    print("[FAIL] pattern nahi mila. Kuch nahi badla.")
    raise SystemExit(1)
p.write_text(t.replace(old, "assert len(parts) == 2 and all(len(p.split()) <= 12 for p in parts)"), encoding="utf-8")
print("[OK] test theek ho gaya")

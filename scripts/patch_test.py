from pathlib import Path
p = Path("tests/test_dashboard_ops.py")
s = p.read_text(encoding="utf-8")
old = "    assert len(app.metric) == 3"
new = ("    labels = [m.label for m in app.metric]\n"
       "    assert len(app.metric) == 4\n"
       "    assert \"Videos (stats ke saath)\" in labels\n"
       "    assert \"Total videos\" in labels")
if old in s:
    p.write_text(s.replace(old, new, 1), encoding="utf-8")
    print("Patched: tests/test_dashboard_ops.py")
else:
    print("Line nahi mili, patch skip")

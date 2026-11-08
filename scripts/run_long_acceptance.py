"""Task 36 acceptance run: topic se poori long-form episode + report.
Usage: python -m scripts.run_long_acceptance "topic" [--minutes 10] [--language English] [--run <folder>]
Dobara chalane par wahi --run folder do, resume hoga. Gemini key aur Pixabay key chahiye."""
import argparse
import json
import re
import time
from pathlib import Path

import httpx

from app.services import long_pipeline as lp
from app.services.long_script import make_client

root = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("topic")
ap.add_argument("--minutes", type=float, default=10.0)
ap.add_argument("--language", default="English")
ap.add_argument("--run", default=None)
a = ap.parse_args()

slug = re.sub(r"[^a-z0-9]+", "_", a.topic.lower()).strip("_")[:40]
run = Path(a.run) if a.run else root / "output" / "long_test" / f"acceptance_{slug}"
run.mkdir(parents=True, exist_ok=True)

client = make_client()
began = time.time()
stage_times, last = {}, {"t": began, "stage": None}
orig = lp.write_progress


def tracked(r, **kw):
    st = kw.get("stage")
    if st and st != last["stage"]:
        if last["stage"]:
            stage_times[last["stage"]] = round(time.time() - last["t"], 1)
        last.update(t=time.time(), stage=st)
    return orig(r, **kw)


lp.write_progress = tracked
error = None
result = None
try:
    with httpx.Client(timeout=60) as http:
        result = lp.run_long_pipeline(a.topic, a.language, a.minutes, run, client, http)
except Exception as exc:
    error = f"{type(exc).__name__}: {exc}"
if last["stage"]:
    stage_times[last["stage"]] = round(time.time() - last["t"], 1)

def load(name):
    f = run / name
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}

render, qa, pkg = load("render/render_report.json"), load("long_quality.json"), load("long_package.json")
dur = render.get("actual_seconds", 0)
errors = [i for i in qa.get("issues", []) if i.get("level") == "error"]
checks = {
    "pipeline_completed": error is None,
    "size_1920x1080": (render.get("width"), render.get("height")) == (1920, 1080),
    "duration_10_to_20_min": 570 <= dur <= 1200,
    "qa_zero_errors": error is None and not errors,
    "thumbnail_exists": bool(pkg.get("thumbnail_path")) and Path(pkg.get("thumbnail_path", "x")).is_file(),
    "seo_ready": bool(pkg.get("title")) and len(pkg.get("tags", [])) >= 5 and bool(pkg.get("description")),
    "chapters_present": len(pkg.get("chapters", [])) >= 3,
}
report = {
    "topic": a.topic, "run_dir": str(run), "error": error,
    "runtime_minutes": round((time.time() - began) / 60, 1), "stage_seconds": stage_times,
    "gemini_requests_this_run": getattr(client, "requests_made", None),
    "video_seconds": dur, "render": render,
    "qa": {"errors": len(errors), "warnings": len([i for i in qa.get("issues", []) if i.get("level") == "warning"]),
           "issues": qa.get("issues", [])},
    "package": {"title": pkg.get("title"), "chapters": len(pkg.get("chapters", [])),
                "tags": len(pkg.get("tags", [])), "warnings": pkg.get("warnings", [])},
    "checks": checks, "passed": all(checks.values()),
}
(run / "acceptance_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print("\n=== ACCEPTANCE ===")
for k, v in checks.items():
    print(f"  [{'OK' if v else 'FAIL'}] {k}")
print(f"Runtime: {report['runtime_minutes']} min | Gemini requests: {report['gemini_requests_this_run']} | Video: {dur:.0f}s")
if error:
    print("Error  :", error, "\n(Dobara chalane par resume hoga: --run", run, ")")
print("Report :", run / "acceptance_report.json")



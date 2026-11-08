import pytest
from types import SimpleNamespace as NS

from app.services import long_pipeline as lp
from app.services.long_package import LongPackage
from app.services.long_quality import QAReport


def test_progress_failure_and_rerun(tmp_path):
    def ok(c): pass
    def boom(c): raise RuntimeError("x")
    c = NS(run=tmp_path)
    with pytest.raises(RuntimeError):
        lp.run_stages(c, [("a", ok), ("b", boom)])
    pr = lp.read_progress(tmp_path)
    assert pr["status"] == "failed" and pr["stage"] == "b" and pr["error"] == "x"
    lp.run_stages(c, [("a", ok), ("b", ok)])
    assert lp.read_progress(tmp_path)["status"] == "done" and lp.read_progress(tmp_path)["pct"] == 100


def test_to_result_for_publisher(tmp_path):
    pkg = LongPackage(title="T", description="Body\n\nChapters:\n0:00 A\n\n#Space #Stars", hashtags=["#Space", "#Stars"],
                      tags=["a"], thumbnail_text="x", thumbnail_path="t.jpg")
    c = NS(topic="t", language="English", run=tmp_path, video=tmp_path / "v.mp4", pkg=pkg,
           qa=QAReport(stats={"duration": 61.0}), needs_review=False)
    r = lp.to_result(c)
    assert r.status == "ready" and r.duration == 61.0 and r.seo.full_description.count("#Space") == 1
    c.needs_review = True
    assert lp.to_result(c).status == "needs_review"

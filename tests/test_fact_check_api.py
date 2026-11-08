import json

from app.api.main import load_fact_check


def test_load_fact_check_reads_file(tmp_path):
    (tmp_path / "fact_check.json").write_text(json.dumps({"checked": True, "claims": []}), encoding="utf-8")
    assert load_fact_check(str(tmp_path)) == {"checked": True, "claims": []}


def test_load_fact_check_missing_or_bad(tmp_path):
    assert load_fact_check(None) is None
    assert load_fact_check(str(tmp_path)) is None
    (tmp_path / "fact_check.json").write_text("{kharab", encoding="utf-8")
    assert load_fact_check(str(tmp_path)) is None

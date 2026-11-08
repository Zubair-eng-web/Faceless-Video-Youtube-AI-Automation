import pytest

from scripts import readme_update as R

SAMPLE = """# Title

Halat: Step 13 tak mukammal (neeche dekhein).

| # | Feature | Halat | Tafseel |
|---|---|---|---|
| 7 | Animated Captions   |  DONE | purani tafseel |
| 12 | Multilingual | PARTIAL | purani |

| Production ek baar chalana | `python -m scripts.run_production_once` |

Step 13 par 285 tests hone chahiye.

### Step 13: Kuch
- Total 285 tests.

<!-- STEPS-LOG-END -->
"""


def test_set_status_line():
    assert "Halat: Step 14 tak mukammal" in R.set_status_line(SAMPLE, 14)


def test_set_feature_row_works_even_when_table_was_reformatted():
    text = R.set_feature_row(SAMPLE, 7, "Animated Captions", "DONE", "nayi tafseel")
    assert "| 7 | Animated Captions | DONE | nayi tafseel |" in text
    assert "purani tafseel" not in text
    with pytest.raises(ValueError):
        R.set_feature_row(SAMPLE, 99, "Kuch", "DONE", "x")


def test_insert_after_line_is_idempotent():
    rows = ["| Naya kaam | `python -m scripts.naya` |"]
    once = R.insert_after_line(SAMPLE, r"scripts\.run_production_once", rows)
    twice = R.insert_after_line(once, r"scripts\.run_production_once", rows)
    assert once == twice
    assert once.count("scripts.naya") == 1
    with pytest.raises(ValueError):
        R.insert_after_line(SAMPLE, "nahi milega", rows)


def test_add_step_entry_inserts_before_marker_once():
    entry = "### Step 14: Test\n- kuch bana"
    once = R.add_step_entry(SAMPLE, entry)
    assert once.index("### Step 14: Test") < once.index(R.STEPS_MARKER)
    assert R.add_step_entry(once, entry) == once
    with pytest.raises(ValueError):
        R.add_step_entry("koi marker nahi", entry)


def test_sub_text_and_optional_miss():
    text = R.sub_text(SAMPLE, r"Step \d+ par \d+ tests", "Step 14 par 336 tests")
    assert "Step 14 par 336 tests hone chahiye." in text
    assert R.sub_text(SAMPLE, "nahi milega", "x", required=False) == SAMPLE
    with pytest.raises(ValueError):
        R.sub_text(SAMPLE, "nahi milega", "x")


def test_parse_collected():
    assert R.parse_collected("a\nb\n317 tests collected in 0.60s\n") == 317
    assert R.parse_collected("1 test collected in 0.01s") == 1
    with pytest.raises(ValueError):
        R.parse_collected("kuch nahi")

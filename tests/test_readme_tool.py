import pytest

from scripts import readme_tool as T

SAMPLE = """# T

Status: 1 long-form upgrade task complete; 2 remaining.

<!-- PROGRESS-START -->
<!-- PROGRESS-END -->

<!-- DONE-START -->
| # | Task | Completed work |
|---|---|---|
| 1 | Pehla | kuch |
<!-- DONE-END -->

<!-- TODO-START -->
| # | Task | Details | Requirement |
|---|---|---|---|
| 2 | Doosra | tafseel | Req 1 |
| 3 | Teesra | tafseel | Req 2 |
<!-- TODO-END -->

<!-- BACKLOG-START -->
| Item | Details |
|---|---|
| Login | security |
<!-- BACKLOG-END -->

<!-- AUTO-STRUCTURE-START -->
<!-- AUTO-STRUCTURE-END -->
<!-- AUTO-API-START -->
<!-- AUTO-API-END -->
<!-- AUTO-DASHBOARD-START -->
<!-- AUTO-DASHBOARD-END -->
<!-- AUTO-SCRIPTS-START -->
<!-- AUTO-SCRIPTS-END -->
<!-- AUTO-ENV-START -->
<!-- AUTO-ENV-END -->

### Step 1: Pehla
- bullet

<!-- STEPS-LOG-END -->
"""


def make_project(tmp_path):
    api = tmp_path / "app" / "api"
    core = tmp_path / "app" / "core"
    services = tmp_path / "app" / "services"
    dash = tmp_path / "dashboard"
    scripts = tmp_path / "scripts"
    for folder in (api, core, services, dash, scripts):
        folder.mkdir(parents=True)
    (api / "main.py").write_text('@app.get("/health")\n@app.post("/generate")\n@app.get("/health")\n', encoding="utf-8")
    (core / "config.py").write_text(
        "class Settings(BaseSettings):\n    gemini_api_key: str = ''\n    video_width: int = 1080\n"
        "    output_dir: Path = BASE_DIR / 'output'\n", encoding="utf-8")
    (services / "alpha.py").write_text(
        "import os\nA = os.environ.get('LONG_MAX_SCENES', '150')\nB = _env('LONG_MIN_MINUTES', 10)\n"
        "C = os.environ.get('MY_API_KEY', 'abc')\nD = d.get('lowercase', 1)\nE = x.get('SINGLE')\n", encoding="utf-8")
    (dash / "streamlit_app.py").write_text('PAGES = ["Videos", "Generate"]\n', encoding="utf-8")
    (scripts / "make_video.py").write_text('\ufeff"""Topic se video banata hai.\n\nLambi tafseel."""\n', encoding="utf-8")
    (scripts / "patch_old.py").write_text('"""Purana patch."""\n', encoding="utf-8")
    (scripts / "readme_step3.py").write_text('"""Purana readme."""\n', encoding="utf-8")
    (scripts / "__init__.py").write_text("", encoding="utf-8")
    return tmp_path


def test_table_roundtrip_and_pipe_cleaning():
    table = T.render_table(["#", "Task"], [["1", "a | b"], ["2", "c"]])
    assert T.parse_table(table) == [["1", "a / b"], ["2", "c"]]


def test_set_block_replaces_only_inside_markers():
    text = T.set_block(SAMPLE, "AUTO-API", "NAYA")
    assert T.get_block(text, "AUTO-API") == "NAYA"
    assert T.get_block(text, "AUTO-ENV") == ""
    assert "### Step 1: Pehla" in text


def test_missing_markers_raise():
    with pytest.raises(ValueError):
        T.get_block("kuch nahi", "DONE")


def test_complete_task_moves_row_and_updates_progress():
    text = T.complete_task(SAMPLE, 2, "Doosra", "bana diya", ["bullet a", "bullet b"], tests=100)
    assert [r[0] for r in T.get_rows(text, "DONE")] == ["1", "2"]
    assert [r[0] for r in T.get_rows(text, "TODO")] == ["3"]
    block = T.get_block(text, "PROGRESS")
    assert "Complete: 2 | Remaining: 1 | Backlog: 1" in block
    assert "Tests: 100" in block
    assert "Status: 2 long-form upgrade tasks complete; 1 remaining." in text
    assert text.index("### Step 2: Doosra") < text.index(T.STEPS_MARKER)
    assert "- Total 100 tests." in text


def test_complete_task_is_idempotent_and_replaces_entry():
    once = T.complete_task(SAMPLE, 2, "Doosra", "pehla", ["purani baat"])
    twice = T.complete_task(once, 2, "Doosra", "doosra", ["nayi baat"])
    assert len(T.get_rows(twice, "DONE")) == 2
    assert twice.count("### Step 2:") == 1
    assert "nayi baat" in twice and "purani baat" not in twice


def test_add_todo_keeps_numeric_order():
    text = T.add_todo(SAMPLE, 10, "Das", "tafseel", "Req 5")
    text = T.add_todo(text, 4, "Chaar", "tafseel")
    assert [r[0] for r in T.get_rows(text, "TODO")] == ["2", "3", "4", "10"]


def test_refresh_progress_keeps_test_count():
    text = T.refresh_progress(SAMPLE, tests=77)
    assert "Tests: 77" in T.get_block(text, "PROGRESS")
    assert "Tests: 77" in T.get_block(T.refresh_progress(text), "PROGRESS")


def test_parse_tests():
    assert T.parse_tests("448 tests collected in 3.15s") == 448
    assert T.parse_tests("1 test collected") == 1
    assert T.parse_tests("kuch nahi") is None


def test_sync_builds_routes_pages_and_structure(tmp_path):
    text = T.sync(SAMPLE, make_project(tmp_path))
    api = T.get_block(text, "AUTO-API")
    assert api.count("/health") == 1
    assert "| POST | /generate |" in api
    assert "Pages: Videos, Generate" in T.get_block(text, "AUTO-DASHBOARD")
    structure = T.get_block(text, "AUTO-STRUCTURE")
    assert "app/services/" in structure and "alpha" in structure
    assert "app/api/" in structure and "main" in structure


def test_sync_env_scan_and_settings(tmp_path):
    env = T.get_block(T.sync(SAMPLE, make_project(tmp_path)), "AUTO-ENV")
    assert "| `LONG_MAX_SCENES` | 150 |" in env
    assert "| `LONG_MIN_MINUTES` | 10 |" in env
    assert "| `MY_API_KEY` | (secret) |" in env
    assert "| `GEMINI_API_KEY` | (secret) |" in env
    assert "| `VIDEO_WIDTH` | 1080 |" in env
    assert "| `OUTPUT_DIR` | (computed) |" in env
    assert "lowercase" not in env and "SINGLE" not in env


def test_sync_scripts_skip_one_off_files(tmp_path):
    scripts = T.get_block(T.sync(SAMPLE, make_project(tmp_path)), "AUTO-SCRIPTS")
    assert "scripts.make_video" in scripts
    assert "Topic se video banata hai." in scripts
    assert "patch_old" not in scripts and "readme_step3" not in scripts


def test_sync_is_idempotent(tmp_path):
    root = make_project(tmp_path)
    once = T.sync(SAMPLE, root, tests=5)
    assert T.sync(once, root) == once

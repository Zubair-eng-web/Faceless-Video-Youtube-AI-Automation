from dashboard.helpers import (
    can_approve,
    can_reject,
    channel_options,
    description_text,
    format_duration,
    is_active,
    quality_summary,
    status_label,
    video_label,
    video_rows,
)


def video(**kwargs):
    base = dict(id=1, channel_id=1, topic="Moon", language="English", status="ready", title="Moon Silence",
                duration=20.47, error=None, created_at="2026-11-06T09:00:00")
    base.update(kwargs)
    return base


def test_status_label_known_and_unknown():
    assert "ready" in status_label("ready")
    assert status_label("weird") == "weird"


def test_format_duration():
    assert format_duration(20.47) == "20.5s"
    assert format_duration(None) == "-"


def test_video_rows_use_channel_name_and_fallbacks():
    rows = video_rows(
        [video(), video(id=2, channel_id=None, title=None, topic="", status="queued", duration=None)],
        {1: "Space"},
    )
    assert rows[0]["Channel"] == "Space"
    assert rows[0]["Title"] == "Moon Silence"
    assert rows[0]["Duration"] == "20.5s"
    assert rows[0]["Created"] == "2026-11-06 09:00:00"
    assert rows[1]["Channel"] == "-"
    assert rows[1]["Title"] == "(topic chuna ja raha hai)"
    assert rows[1]["Duration"] == "-"


def test_video_label_prefers_title_then_topic():
    assert video_label(video()) == "#1 - Moon Silence [ready]"
    assert video_label(video(title=None)) == "#1 - Moon [ready]"


def test_channel_options():
    assert channel_options([{"id": 3, "name": "Space"}]) == {"Space (id 3)": 3}


def test_quality_summary_with_issues():
    quality = {"issues": [
        {"level": "error", "code": "black_frames", "message": "kala"},
        {"level": "warning", "code": "quiet_audio", "message": "halki"},
    ]}
    headline, lines = quality_summary(quality)
    assert headline == "FAIL (1 errors, 1 warnings)"
    assert lines[0] == "[ERROR] black_frames: kala"


def test_quality_summary_pass_and_missing():
    assert quality_summary({"issues": []})[0] == "PASS (0 errors, 0 warnings)"
    assert quality_summary(None) == ("-", [])


def test_review_rules_and_active():
    assert can_approve("ready") and can_approve("needs_review")
    assert not can_approve("approved") and not can_approve("failed")
    assert can_reject("approved") and can_reject("ready")
    assert not can_reject("rejected") and not can_reject("queued")
    assert is_active({"status": "generating"})
    assert not is_active({"status": "ready"})


def test_description_text_appends_hashtags():
    assert description_text({"description": "Hello", "hashtags": ["#Shorts", "#moon"]}) == "Hello\n\n#Shorts #moon"

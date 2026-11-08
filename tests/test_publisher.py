from datetime import datetime, timedelta

import pytest

from app.agents.seo_agent import SEOPack
from app.core import db, db_publish
from app.pipeline import PipelineResult
from app.services import publisher
from app.services.publisher import PublishError, execute_publish, prepare_publish, publish_due, run_publish
from app.services.quality import QualityReport
from app.services.youtube import YouTubeError, YouTubeQuotaError

PAST = "2000-01-01T00:00"
FUTURE = "2999-01-01T00:00"


@pytest.fixture(autouse=True)
def reset_quota():
    publisher.QUOTA_STATE["until"] = None
    yield
    publisher.QUOTA_STATE["until"] = None


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "app.db"
    db.init_db(p)
    db.create_channel(p, "C")  # id 1
    return p


class Uploader:
    def __init__(self, errors=None, thumb_error=None):
        self.errors = list(errors or [])
        self.thumb_error = thumb_error
        self.calls = []

    def __call__(self, channel_id, video_path, title, description, tags=(), thumbnail_path=None,
                 privacy="private", **kwargs):
        self.calls.append(dict(channel_id=channel_id, video_path=video_path, title=title,
                               description=description, tags=list(tags), privacy=privacy))
        error = self.errors.pop(0) if self.errors else None
        if error:
            raise error
        return {"video_id": f"yt{len(self.calls)}", "thumbnail_error": self.thumb_error}


def make_approved(path, tmp_path, topic="A", channel_id=1, with_file=True, scheduled=None):
    video_file = tmp_path / f"{topic}.mp4"
    if with_file:
        video_file.write_bytes(b"x")
    result = PipelineResult(
        topic=topic, language="English", status="ready", run_dir=str(tmp_path), video_path=str(video_file),
        thumbnail_path=str(tmp_path / "t.jpg"), title="Title", duration=20.0,
        seo=SEOPack(title=f"Title {topic}", description="Desc", hashtags=["#Shorts", "#space"],
                    tags=["space"], thumbnail_text="BOOM"),
        quality=QualityReport(issues=[], stats={}),
    )
    video_id = db.create_job(path, channel_id, topic, "English")
    db.transition(path, video_id, "generating", {"queued"})
    db.finish_video(path, video_id, result)
    db.transition(path, video_id, "approved", {"ready"})
    if scheduled:
        db_publish.schedule_video(path, video_id, scheduled)
    return video_id


def test_prepare_publish_rejects_bad_videos(path, tmp_path):
    queued = db.create_job(path, 1, "Q", "English")
    with pytest.raises(db.InvalidTransitionError):
        prepare_publish(path, queued)
    no_channel = make_approved(path, tmp_path, "B", channel_id=None)
    with pytest.raises(PublishError):
        prepare_publish(path, no_channel)
    no_file = make_approved(path, tmp_path, "C", with_file=False)
    with pytest.raises(PublishError):
        prepare_publish(path, no_file)
    assert db.get_video(path, no_channel)["status"] == "approved"
    with pytest.raises(db.NotFoundError):
        prepare_publish(path, 999)


def test_prepare_publish_claims_video(path, tmp_path):
    video_id = make_approved(path, tmp_path)
    assert prepare_publish(path, video_id)["status"] == "publishing"


def test_execute_publish_success(path, tmp_path):
    video_id = make_approved(path, tmp_path)
    uploader = Uploader()
    row = execute_publish(path, prepare_publish(path, video_id), uploader, "unlisted")
    assert row["status"] == "published"
    assert row["youtube_id"] == "yt1"
    assert row["privacy"] == "unlisted"
    call = uploader.calls[0]
    assert call["channel_id"] == 1
    assert call["title"] == "Title A"
    assert call["description"] == "Desc\n\n#Shorts #space"
    assert call["tags"] == ["space"]
    assert call["privacy"] == "unlisted"


def test_execute_publish_saves_thumbnail_note(path, tmp_path):
    video_id = make_approved(path, tmp_path)
    row = execute_publish(path, prepare_publish(path, video_id), Uploader(thumb_error="verify nahi"), "private")
    assert row["status"] == "published"
    assert "Thumbnail" in row["publish_error"]


def test_execute_publish_failure_is_recorded(path, tmp_path):
    video_id = make_approved(path, tmp_path)
    with pytest.raises(YouTubeError):
        execute_publish(path, prepare_publish(path, video_id), Uploader(errors=[YouTubeError("boom")]), "private")
    video = db.get_video(path, video_id)
    assert video["status"] == "publish_failed"
    assert "boom" in video["publish_error"]


def test_quota_error_returns_video_to_approved(path, tmp_path):
    video_id = make_approved(path, tmp_path)
    with pytest.raises(YouTubeQuotaError):
        execute_publish(path, prepare_publish(path, video_id), Uploader(errors=[YouTubeQuotaError("limit")]), "private")
    video = db.get_video(path, video_id)
    assert video["status"] == "approved"
    assert "limit" in video["publish_error"]


def test_run_publish_swallows_errors(path, tmp_path):
    video_id = make_approved(path, tmp_path)
    claimed = prepare_publish(path, video_id)
    run_publish(path, claimed, Uploader(errors=[YouTubeError("boom")]), "private")
    assert db.get_video(path, video_id)["status"] == "publish_failed"


def test_publish_due_only_publishes_due_videos(path, tmp_path):
    due = make_approved(path, tmp_path, "A", scheduled=PAST)
    later = make_approved(path, tmp_path, "B", scheduled=FUTURE)
    manual = make_approved(path, tmp_path, "C")
    uploader = Uploader()
    assert publish_due(path, uploader) == [due]
    assert len(uploader.calls) == 1
    assert db.get_video(path, later)["status"] == "approved"
    assert db.get_video(path, manual)["status"] == "approved"


def test_publish_due_respects_daily_limit(path, tmp_path):
    ids = [make_approved(path, tmp_path, name, scheduled=PAST) for name in "ABC"]
    uploader = Uploader()
    assert len(publish_due(path, uploader, daily_limit=2)) == 2
    assert publish_due(path, uploader, daily_limit=2) == []
    assert db.get_video(path, ids[2])["status"] == "approved"


def test_publish_due_pauses_after_quota_error(path, tmp_path):
    make_approved(path, tmp_path, "A", scheduled=PAST)
    make_approved(path, tmp_path, "B", scheduled=PAST)
    uploader = Uploader(errors=[YouTubeQuotaError("limit")])
    base = datetime.now()
    assert publish_due(path, uploader, now=lambda: base) == []
    assert len(uploader.calls) == 1
    assert publish_due(path, uploader, now=lambda: base + timedelta(minutes=30)) == []
    assert len(uploader.calls) == 1
    done = publish_due(path, uploader, now=lambda: base + timedelta(hours=2))
    assert len(done) == 2
    assert len(uploader.calls) == 3


def test_publish_due_marks_unpublishable_video_failed_and_continues(path, tmp_path):
    bad = make_approved(path, tmp_path, "A", channel_id=None, scheduled="2000-01-01T00:00")
    good = make_approved(path, tmp_path, "B", scheduled="2000-01-02T00:00")
    assert publish_due(path, Uploader()) == [good]
    assert db.get_video(path, bad)["status"] == "publish_failed"


def test_publish_due_does_nothing_when_nothing_is_due(path, tmp_path):
    make_approved(path, tmp_path, "A", scheduled=FUTURE)
    uploader = Uploader()
    assert publish_due(path, uploader) == []
    assert uploader.calls == []

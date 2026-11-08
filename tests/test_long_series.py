from types import SimpleNamespace as NS

from app.core import db, db_series as ds


def _setup(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    ch = db.create_channel(p, "Space")
    return p, ch["id"]


def test_series_episodes_increment(tmp_path):
    p, cid = _setup(tmp_path)
    s = ds.create_series(p, "Cosmos", channel_id=cid, visual={"transition": 0.6})
    v1, v2 = db.create_job(p, cid, "a", "English"), db.create_job(p, cid, "b", "English")
    assert ds.attach_episode(p, v1, s["id"]) == 1 and ds.attach_episode(p, v2, s["id"]) == 2
    assert db.get_video(p, v2)["episode_no"] == 2
    assert ds.series_transition(ds.get_series(p, s["id"])) == 0.6


def test_structure_reused_in_style(tmp_path):
    p, cid = _setup(tmp_path)
    s = ds.create_series(p, "Cosmos", channel_id=cid, tone="warm")
    script = NS(minutes=10, chapters=[NS(words=300, title="A"), NS(words=500, title="B")])
    assert ds.save_structure(p, s["id"], script)["chapter_words"] == 400
    style = ds.series_style(ds.get_series(p, s["id"]), episode=2)
    assert style.name == "Cosmos" and style.episode == 2 and "2 chapters" in style.tone and style.tone.startswith("warm")
    assert ds.list_series(p, cid)[0]["name"] == "Cosmos"

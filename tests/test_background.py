import asyncio

from app.core.config import Settings
from app.services import background
from app.services import scheduler as sched


class FakeScheduler:
    instances = []

    def __init__(self):
        self.jobs = []
        self.started = False
        self.stopped = False
        FakeScheduler.instances.append(self)

    def add_job(self, func, trigger, **kwargs):
        self.jobs.append((func, trigger, kwargs))

    def start(self):
        self.started = True

    def shutdown(self, wait=True):
        self.stopped = True


def run_lifespan(lifespan):
    async def go():
        async with lifespan(None):
            pass

    asyncio.run(go())


def test_build_jobs_has_publish_and_produce(monkeypatch):
    calls = []
    monkeypatch.setattr(background, "produce_due", lambda db_path, runner: calls.append((db_path, runner)))
    jobs = background.build_jobs("db", "runner", lambda: None, True, False)
    assert [(j.name, j.enabled) for j in jobs] == [("publish", True), ("produce", False)]
    jobs[1].func()
    assert calls == [("db", "runner")]


def test_multi_lifespan_starts_only_enabled_jobs(monkeypatch):
    FakeScheduler.instances = []
    monkeypatch.setattr(sched, "BackgroundScheduler", FakeScheduler)
    jobs = [sched.Job("publish", lambda: None, 5, True), sched.Job("produce", lambda: None, 10, False)]
    run_lifespan(sched.make_multi_lifespan(jobs))
    scheduler = FakeScheduler.instances[0]
    assert scheduler.started and scheduler.stopped
    assert [kwargs["id"] for _, _, kwargs in scheduler.jobs] == ["publish"]


def test_multi_lifespan_without_enabled_jobs_creates_nothing(monkeypatch):
    FakeScheduler.instances = []
    monkeypatch.setattr(sched, "BackgroundScheduler", FakeScheduler)
    run_lifespan(sched.make_multi_lifespan([sched.Job("produce", lambda: None, 10, False)]))
    assert FakeScheduler.instances == []


def test_settings_production_defaults():
    settings = Settings(_env_file=None)
    assert settings.auto_produce is False
    assert settings.produce_check_minutes == 10

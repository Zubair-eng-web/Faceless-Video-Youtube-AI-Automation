import asyncio

import pytest

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


@pytest.fixture(autouse=True)
def fake_scheduler(monkeypatch):
    FakeScheduler.instances = []
    monkeypatch.setattr(sched, "BackgroundScheduler", FakeScheduler)


def run_lifespan(lifespan):
    async def go():
        async with lifespan(None):
            pass

    asyncio.run(go())


def test_safe_job_swallows_errors():
    def boom():
        raise RuntimeError("x")

    sched.safe_job(boom)()


def test_disabled_scheduler_is_not_created():
    run_lifespan(sched.make_lifespan(lambda: None, 5, False))
    assert FakeScheduler.instances == []


def test_enabled_scheduler_starts_and_stops():
    run_lifespan(sched.make_lifespan(lambda: None, 5, True))
    scheduler = FakeScheduler.instances[0]
    assert scheduler.started and scheduler.stopped
    assert scheduler.jobs[0][1] == "interval"
    assert scheduler.jobs[0][2]["minutes"] == 5


def test_minimum_interval_is_one_minute():
    run_lifespan(sched.make_lifespan(lambda: None, 0, True))
    assert FakeScheduler.instances[0].jobs[0][2]["minutes"] == 1

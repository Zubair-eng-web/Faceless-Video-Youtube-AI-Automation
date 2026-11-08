"""Background scheduler: publish aur production ke jobs."""
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler


@dataclass
class Job:
    name: str
    func: Callable
    minutes: int
    enabled: bool = True


def safe_job(job):
    def wrapper():
        try:
            job()
        except Exception as exc:  # scheduler kabhi band nahi hona chahiye
            print("Background job me error:", exc, flush=True)

    return wrapper


def make_multi_lifespan(jobs):
    @asynccontextmanager
    async def lifespan(app):
        scheduler = None
        active = [j for j in jobs if j.enabled]
        if active:
            scheduler = BackgroundScheduler()
            for index, job in enumerate(active):
                minutes = max(1, job.minutes)
                scheduler.add_job(
                    safe_job(job.func), "interval", minutes=minutes, max_instances=1, coalesce=True,
                    id=job.name, next_run_time=datetime.now() + timedelta(seconds=20 + 10 * index),
                )
                print(f"Auto {job.name} ON: har {minutes} minute baad check hoga.", flush=True)
            scheduler.start()
        try:
            yield
        finally:
            if scheduler is not None:
                scheduler.shutdown(wait=False)

    return lifespan


def make_lifespan(job, minutes: int, enabled: bool):
    return make_multi_lifespan([Job("publish", job, minutes, enabled)])

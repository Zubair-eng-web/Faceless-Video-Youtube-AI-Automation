import os
import sqlite3
import time
from datetime import datetime, timedelta

import pytest

from app.services.maintenance import backup_db, delete_runs, find_deletable_runs, rotate_logs


def _db(path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE t (x INTEGER)")
    con.execute("INSERT INTO t VALUES (42)")
    con.commit()
    con.close()


def test_backup_prunes_old_and_is_readable(tmp_path):
    src = tmp_path / "app.db"
    _db(src)
    base = datetime(2026, 1, 1)
    clock = iter(base + timedelta(seconds=i) for i in range(10))
    last = None
    for _ in range(3):
        last = backup_db(src, tmp_path / "b", keep=2, now=lambda: next(clock))
    files = sorted((tmp_path / "b").glob("app_*.db"))
    assert len(files) == 2 and last == files[-1]
    assert sqlite3.connect(last).execute("SELECT x FROM t").fetchone() == (42,)


def test_backup_missing_db_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        backup_db(tmp_path / "nahi.db")


def _mk(root, name, age_days):
    d = root / name
    d.mkdir(parents=True)
    f = d / "x.bin"
    f.write_bytes(b"x" * 10)
    t = time.time() - age_days * 86400
    os.utime(f, (t, t))
    os.utime(d, (t, t))
    return d


def test_find_and_delete_runs(tmp_path):
    runs = tmp_path / "runs"
    dirs = {n: _mk(runs, n, a) for n, a in [("pub", 30), ("fail", 30), ("orphan", 30), ("newfail", 1),
                                           ("ready", 30), ("review", 30)]}
    videos = [{"run_dir": str(dirs["pub"]), "status": "published"}, {"run_dir": str(dirs["fail"]), "status": "failed"},
              {"run_dir": str(dirs["newfail"]), "status": "failed"}, {"run_dir": str(dirs["ready"]), "status": "ready"},
              {"run_dir": str(dirs["review"]), "status": "needs_review"}]
    items = find_deletable_runs(runs, videos, days=14)
    assert {i["path"].name for i in items} == {"fail", "orphan"} and items[0]["bytes"] == 10
    assert delete_runs(items) == 2
    assert dirs["pub"].exists() and dirs["ready"].exists() and not dirs["fail"].exists()
    assert find_deletable_runs(tmp_path / "nahi", []) == []


def test_rotate_logs(tmp_path):
    (tmp_path / "api.log").write_bytes(b"x" * 100)
    (tmp_path / "small.log").write_bytes(b"x")
    assert rotate_logs(tmp_path, max_bytes=50) == ["api.log"]
    assert (tmp_path / "api.log.old").exists() and not (tmp_path / "api.log").exists()
    assert (tmp_path / "small.log").exists() and rotate_logs(tmp_path / "nahi") == []

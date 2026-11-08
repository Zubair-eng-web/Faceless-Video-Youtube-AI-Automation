"""Maintenance: database backup, log rotation, purane run folders ki safai."""
import os
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DELETABLE_STATUSES = {"rejected", "failed", "orphan"}  # orphan = database mein jis ka record nahi


def backup_db(db_path, backup_dir=None, keep: int = 7, now=datetime.now) -> Path:
    src = Path(db_path)
    if not src.exists():
        raise FileNotFoundError(f"Database nahi mila: {src}")
    dest_dir = Path(backup_dir) if backup_dir else src.parent / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"app_{now():%Y%m%d_%H%M%S}.db"
    s, d = sqlite3.connect(str(src)), sqlite3.connect(str(dest))
    try:
        s.backup(d)  # chalte database ki bhi mehfooz copy
    finally:
        d.close()
        s.close()
    for old in sorted(dest_dir.glob("app_*.db"))[:-max(keep, 1)]:
        old.unlink(missing_ok=True)
    return dest


def rotate_logs(log_dir, max_bytes: int = 5 * 1024 * 1024) -> list[str]:
    d = Path(log_dir)
    done: list[str] = []
    if not d.exists():
        return done
    for f in d.glob("*.log"):
        try:
            if f.stat().st_size > max_bytes:
                old = f.with_name(f.name + ".old")
                old.unlink(missing_ok=True)
                f.rename(old)
                done.append(f.name)
        except OSError:  # file chal rahi process ke paas khuli ho to chhor do
            continue
    return done


def _folder_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def _latest_mtime(p: Path) -> float:
    times = [p.stat().st_mtime] + [f.stat().st_mtime for f in p.rglob("*")]
    return max(times)


def find_deletable_runs(runs_dir, videos, days: float = 14, now=time.time) -> list[dict]:
    """Sirf rejected/failed/orphan aur `days` se purane folders. Baqi sab (published, ready...) mehfooz."""
    root = Path(runs_dir)
    if not root.exists():
        return []
    status_by = {}
    for v in videos:
        if v.get("run_dir"):
            status_by[str(Path(v["run_dir"]).resolve())] = v.get("status")
    cutoff = now() - days * 86400
    out = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or _latest_mtime(d) > cutoff:
            continue
        status = status_by.get(str(d.resolve()), "orphan")
        if status in DELETABLE_STATUSES:
            out.append({"path": d, "status": status, "bytes": _folder_size(d)})
    return out


def delete_runs(items) -> int:
    n = 0
    for it in items:
        try:
            shutil.rmtree(it["path"])
            n += 1
        except OSError:
            continue
    return n

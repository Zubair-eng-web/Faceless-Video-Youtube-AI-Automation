from types import SimpleNamespace

from app.services.sfx import ensure_whoosh, transition_starts, whoosh_args


def test_transition_starts():
    assert transition_starts([3, 3, 3], 0.5) == [2.4, 4.9]
    assert transition_starts([3], 0.5) == []


def test_whoosh_args_use_noise_source():
    assert any("anoisesrc" in a for a in whoosh_args("x.wav"))


def test_ensure_whoosh_creates_and_reuses(tmp_path):
    calls = []

    def fake(cmd, **kw):
        calls.append(cmd)
        from pathlib import Path
        Path(cmd[-1]).write_bytes(b"x")
        return SimpleNamespace(returncode=0)

    p = ensure_whoosh(tmp_path, fake)
    assert p is not None and p.exists()
    assert ensure_whoosh(tmp_path, fake) == p
    assert len(calls) == 1


def test_ensure_whoosh_returns_none_on_failure(tmp_path):
    assert ensure_whoosh(tmp_path, lambda cmd, **kw: SimpleNamespace(returncode=1)) is None

    def boom(cmd, **kw):
        raise OSError("ffmpeg nahi")

    assert ensure_whoosh(tmp_path / "b", boom) is None

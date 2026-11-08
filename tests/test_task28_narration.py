"""Task 28: long narration (pronunciation, pauses, balance, resume). Asli TTS/ffmpeg nahi, sab fake."""
from pathlib import Path

import pytest

from app.core.models import Scene, Storyboard
from app.services.long_narration import (NarrationConfig, generate_long_voiceover, parse_mean_volume,
                                         prepare_text)
from app.services.long_script import ChapterInfo, LongScript
from app.services.tts import WordTiming


def make_script(n=4):
    scenes = [Scene(number=i + 1, narration="Grew 50% at 300 km/h today", visual_description="v",
                    search_query="q", duration=3) for i in range(n)]
    chapters = [ChapterInfo(title="A", first_scene=1, last_scene=2, words=10),
                ChapterInfo(title="B", first_scene=3, last_scene=4, words=10)]
    return LongScript(storyboard=Storyboard(title="T", hook="h", scenes=scenes), chapters=chapters,
                      minutes=0.1, words=20)


class Fake:
    def __init__(self):
        self.synth_calls, self.texts, self.process_calls, self.durs = 0, [], [], {}
        self.concat, self.normalized = None, None

    async def synth(self, text, voice, rate, path):
        self.synth_calls += 1
        self.texts.append(text)
        Path(path).write_bytes(b"x")
        return [WordTiming(text="w", start=0.1, end=0.5), WordTiming(text="x", start=0.5, end=2.0)]

    def duration(self, p):
        return self.durs.get(str(p), 2.0)

    def measure(self, p):
        return -30.0 if "scene_004" in str(p) else -20.0

    def process(self, p, gain, pad):
        self.process_calls.append((Path(p).stem, gain, pad))
        self.durs[str(p)] = self.durs.get(str(p), 2.0) + pad

    def run(self, tmp, script=None, **kw):
        return generate_long_voiceover(
            script or make_script(), tmp, cfg=NarrationConfig(), synth=self.synth, duration_fn=self.duration,
            trim_fn=lambda *a: None, measure_fn=self.measure, process_fn=self.process,
            concat_fn=lambda paths, out: setattr(self, "concat", [str(p) for p in paths]),
            normalize_fn=lambda p, lufs: setattr(self, "normalized", lufs), sleep=lambda s: None,
            progress=lambda m: None, **kw)


def test_prepare_text_english():
    t = prepare_text("Grew 50% at 300 km/h, e.g. a $5 million probe at 20 \u00b0C & more *bold*")
    assert "50 percent" in t and "kilometers per hour" in t and "5 million dollars" in t
    assert "for example" in t and "20 degrees Celsius" in t and " and more" in t and "*" not in t


def test_prepare_text_other_language_untouched():
    assert prepare_text("50%  km/h", "Hindi") == "50% km/h"


def test_config_rate_validation(monkeypatch):
    monkeypatch.setenv("LONG_VOICE_RATE", "-5%")
    assert NarrationConfig.from_env().rate == "-5%"
    monkeypatch.setenv("LONG_VOICE_RATE", "fast")
    assert NarrationConfig.from_env().rate == "+0%"


def test_parse_mean_volume():
    assert parse_mean_volume("x mean_volume: -23.4 dB y") == -23.4
    assert parse_mean_volume("nothing") is None


def test_pauses_gain_offsets_and_normalize(tmp_path):
    f = Fake()
    vo, rep = f.run(tmp_path)
    assert f.process_calls == [("scene_001", 0.0, 0.15), ("scene_002", 0.0, 0.7),
                               ("scene_003", 0.0, 0.15), ("scene_004", 6.0, 0)]
    assert vo.scenes[1].start_offset == pytest.approx(2.15)
    assert vo.duration == pytest.approx(9.0)
    assert f.normalized == -16.0 and len(f.concat) == 4
    assert rep.gains_applied == 1 and rep.loudness_spread_db == 10.0
    assert "percent" in f.texts[0]
    assert (tmp_path / "narration_report.json").exists() and (tmp_path / "voiceover.json").exists()


def test_resume_skips_done_scenes(tmp_path):
    f = Fake()
    f.run(tmp_path)
    f.run(tmp_path)
    assert f.synth_calls == 4 and len(f.process_calls) == 4


def test_max_scenes_limits_work(tmp_path):
    f = Fake()
    vo, rep = f.run(tmp_path, max_scenes=2)
    assert len(vo.scenes) == 2 and f.synth_calls == 2 and rep.target_seconds is None
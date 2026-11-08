from types import SimpleNamespace as NS

from app.services.long_quality import check_audio_stats, check_captions, check_coverage, parse_audio_stats


def W(t, s, e):
    return NS(text=t, start=s, end=e)


def test_coverage_flags_missing_clip_and_voice(tmp_path):
    f = tmp_path / "c.mp4"
    f.write_bytes(b"x")
    board = NS(scenes=[NS(number=1, narration="a b"), NS(number=2, narration="c d")])
    issues = check_coverage(board, [NS(scene_number=1, path=str(f))], NS(scenes=[NS(number=2)]))
    assert {i.scene for i in issues} == {1, 2} and all(i.level == "error" for i in issues)


def test_captions_flag_bad_timing_and_mismatch():
    board = NS(scenes=[NS(number=1, narration="one two three four five six seven eight nine ten")])
    good = NS(number=1, duration=5.0, words=[W(str(i), i * 0.5, i * 0.5 + 0.4) for i in range(10)])
    assert check_captions(board, NS(scenes=[good])) == []
    bad = NS(number=1, duration=5.0, words=[W("a", 0, 0.2), W("b", 0.1, 0.1)])
    assert len(check_captions(board, NS(scenes=[bad]))) >= 2


def test_audio_stats_parse_and_thresholds():
    err = ("[silencedetect] silence_start: 12.5\n[silencedetect] silence_end: 18 | silence_duration: 5.5\n"
           " mean_volume: -40.0 dB\n max_volume: 0.0 dB")
    st = parse_audio_stats(err)
    assert st["mean_db"] == -40.0 and st["silences"] == [(12.5, 5.5)]
    assert len(check_audio_stats(st)) == 3
    assert check_audio_stats({"mean_db": -20.0, "peak_db": -3.0, "silences": []}) == []

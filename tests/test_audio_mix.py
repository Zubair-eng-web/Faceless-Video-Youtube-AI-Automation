from app.services.audio_mix import build_audio_graph, sfx_filters


def test_voice_only():
    assert build_audio_graph("voice") == ["[voice]alimiter=limit=0.95[aout]"]


def test_music_is_ducked():
    g = ";".join(build_audio_graph("voice", "music"))
    assert "sidechaincompress" in g and "asplit=2" in g
    assert "[vmain][mduck]amix=inputs=2" in g and g.endswith("[aout]")


def test_no_duck():
    g = ";".join(build_audio_graph("voice", "music", duck=False))
    assert "sidechaincompress" not in g and "[voice][music]amix=inputs=2" in g


def test_all_three_inputs():
    g = ";".join(build_audio_graph("voice", "music", "sfx"))
    assert "amix=inputs=3" in g and "[sfx]" in g


def test_sfx_filters():
    assert sfx_filters([], 3) == ([], None)
    parts, label = sfx_filters([1.5], 3)
    assert label == "sfx" and "adelay=1500|1500" in parts[0]
    parts, label = sfx_filters([1.0, 2.0, 3.0], 3)
    j = ";".join(parts)
    assert "asplit=3" in j and "adelay=2000|2000" in j and "amix=inputs=3" in j

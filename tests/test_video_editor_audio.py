from app.services.video_editor import build_filter_complex


def test_voice_only_unchanged():
    fc = build_filter_complex([3, 3, 3])
    assert fc.endswith("[3:a]aresample=44100,aformat=channel_layouts=stereo[aout]")
    assert "sidechaincompress" not in fc


def test_music_without_duck_keeps_old_mix():
    fc = build_filter_complex([3, 3, 3], music=True)
    assert "[voice][music]amix=inputs=2" in fc and "sidechaincompress" not in fc


def test_music_with_duck():
    fc = build_filter_complex([3, 3, 3], music=True, duck=True)
    assert "sidechaincompress" in fc and "[vmain][mduck]amix=inputs=2" in fc


def test_sfx_without_music_uses_next_input():
    fc = build_filter_complex([3, 3, 3], sfx_starts=[2.4, 4.9])
    assert "[4:a]" in fc and "adelay=2400|2400" in fc and "amix=inputs=2" in fc


def test_sfx_with_music_input_index():
    fc = build_filter_complex([3, 3, 3], music=True, duck=True, sfx_starts=[2.4, 4.9])
    assert "[5:a]" in fc and "amix=inputs=3" in fc

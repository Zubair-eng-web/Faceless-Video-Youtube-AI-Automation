import pytest

from app.agents.seo_agent import (
    SEODraft,
    clean_hashtag,
    clean_tags,
    finalize_seo,
    generate_seo,
    normalize_hashtags,
    trim_title,
)
from app.core.models import SceneDraft, ScriptDraft
from app.core.storyboard import build_storyboard


def draft(**kwargs):
    base = dict(title="Black Holes", description="Great video", hashtags=["space"], tags=["space"], thumbnail_text="BOOM")
    base.update(kwargs)
    return SEODraft(**base)


def test_clean_hashtag_removes_symbols_and_spaces():
    assert clean_hashtag(" #Space Facts! ") == "#SpaceFacts"
    assert clean_hashtag("###") == ""


def test_normalize_hashtags_starts_with_shorts_and_dedupes():
    assert normalize_hashtags(["space", "#Space", "Shorts", "nasa"]) == ["#Shorts", "#space", "#nasa"]


def test_normalize_hashtags_limits_count():
    assert len(normalize_hashtags([f"tag{i}" for i in range(20)], max_count=5)) == 5


def test_trim_title_cuts_at_word_boundary():
    title = " ".join(["word"] * 40)
    result = trim_title(title)
    assert len(result) <= 100
    assert result.endswith("word")


def test_trim_title_keeps_short_titles():
    assert trim_title("  Hello   world ") == "Hello world"


def test_clean_tags_dedupes_and_limits_total_length():
    assert clean_tags(["Space", "space", " #nasa ", ""]) == ["Space", "nasa"]
    long_tags = [f"{i}" + "x" * 150 for i in range(5)]
    assert len(clean_tags(long_tags, max_chars=450)) == 2


def test_finalize_seo_cleans_everything():
    pack = finalize_seo(
        draft(
            description="Great video #space\nFollow for more! #Shorts",
            hashtags=["space", "nasa"],
            thumbnail_text="one two three four five six seven",
        )
    )
    assert "#" not in pack.description
    assert pack.hashtags == ["#Shorts", "#space", "#nasa"]
    assert pack.thumbnail_text == "one two three four five"
    assert pack.full_description.endswith("#Shorts #space #nasa")


def test_finalize_seo_thumbnail_falls_back_to_title():
    assert finalize_seo(draft(title="Black Holes Are Weird", thumbnail_text="  ")).thumbnail_text == "Black Holes Are Weird"


def test_finalize_seo_rejects_empty_title():
    with pytest.raises(ValueError):
        finalize_seo(draft(title="   "))


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def generate_json(self, prompt, schema, system=None, temperature=0.9):
        self.calls.append((prompt, schema, system))
        return self.result


def test_generate_seo_prompt_has_narration_and_language():
    board = build_storyboard(
        ScriptDraft(
            title="T",
            hook="h",
            scenes=[SceneDraft(narration="Space is silent.", visual_description="v", search_query="q")],
        ),
        language="Hindi",
    )
    client = FakeClient(draft())
    pack = generate_seo(board, client)
    prompt, schema, _ = client.calls[0]
    assert "Space is silent." in prompt
    assert "Hindi" in prompt
    assert schema is SEODraft
    assert pack.hashtags[0] == "#Shorts"

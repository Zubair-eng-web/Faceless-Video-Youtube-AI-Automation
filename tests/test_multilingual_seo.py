from app.agents.seo_agent import SEODraft, clean_hashtag, finalize_seo

HINDI = "\u0928\u092e\u0938\u094d\u0924\u0947"
HINDI_TAG = "\u0905\u0902\u0924\u0930\u093f\u0915\u094d\u0937"


def test_clean_hashtag_keeps_devanagari_vowel_signs():
    assert clean_hashtag("#" + HINDI) == "#" + HINDI


def test_finalize_seo_removes_hindi_hashtags_from_description():
    draft = SEODraft(title="T", description="Great #" + HINDI_TAG + " more", hashtags=[], tags=[],
                     thumbnail_text="x")
    pack = finalize_seo(draft)
    assert "#" not in pack.description
    assert "more" in pack.description

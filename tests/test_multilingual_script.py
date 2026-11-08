from app.agents.script_agent import generate_script
from app.core.models import SceneDraft, ScriptDraft


class FakeClient:
    def __init__(self):
        self.calls = []

    def generate_json(self, prompt, schema, system=None, temperature=0.9):
        self.calls.append(prompt)
        return ScriptDraft(
            title="T",
            hook="h",
            scenes=[SceneDraft(narration="Hello there", visual_description="v", search_query="q")],
        )


def test_urdu_prompt_asks_for_urdu_script():
    client = FakeClient()
    generate_script("Space", client, language="Urdu")
    assert "Narration language: Urdu" in client.calls[0]
    assert "Roman Urdu" in client.calls[0]


def test_hindi_prompt_asks_for_devanagari():
    client = FakeClient()
    generate_script("Space", client, language="Hindi")
    assert "Devanagari" in client.calls[0]


def test_english_prompt_has_no_script_hint():
    client = FakeClient()
    generate_script("Space", client, language="English")
    assert "Narration language: English\n" in client.calls[0]

import pytest

from vital.data import patient, snapshot
from vital_ai import explain, handoff, sbar
from vital_ai import llm
from vital_ai.llm import guard

ORIGINAL = "High potassium: hold Lisinopril and Spironolactone. Potassium is 5.8 mmol/L. Suggested: Hold both. Repeat the potassium and notify the provider."


def test_sbar_template_has_all_four_parts():
    snap = snapshot("snapshot-potassium-5.8.json")
    rosa = patient(snap, "p1")
    text = sbar(rosa, [a for a in snap.alerts if a.pid == "p1"])
    for part in ("S:", "B:", "A:", "R:"):
        assert part in text
    assert "5.8" in text


def test_explain_and_handoff_work_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    snap = snapshot("snapshot-potassium-5.8.json")
    rosa = patient(snap, "p1")
    alert = next(a for a in snap.alerts if a.id == "k:p1")
    assert "potassium" in explain(alert, rosa).lower()
    assert rosa.name in handoff(rosa, snap.alerts)
    assert llm.LAST_SOURCE.get() == "template"


# ---- guard ------------------------------------------------------------------------------
def test_guard_accepts_a_faithful_rewrite():
    ok = "Potassium is high at 5.8 mmol/L. Hold Lisinopril and Spironolactone, repeat the potassium, and notify the provider."
    assert guard(ORIGINAL, ok) == ok


@pytest.mark.parametrize("bad", [
    "Potassium is 6.8 mmol/L. Hold Lisinopril and Spironolactone, repeat it and notify the provider.",       # changed number
    "Potassium is 5.8. Hold Lisinopril and Spironolactone, give Furosemide, repeat and notify the provider.",  # new drug
    "Minor issue: potassium 5.8. Hold Lisinopril and Spironolactone, repeat and notify the provider.",       # softer severity
    "Potassium is 5.8 mmol/L. Lisinopril and Spironolactone raise it. Repeat the potassium.",                # dropped hold + notify
    "",                                                                                                        # empty
])
def test_guard_rejects_changed_facts(bad):
    assert guard(ORIGINAL, bad) == ORIGINAL


def test_llm_output_goes_through_guard(monkeypatch):
    """Simulate the model: a faithful answer is used, an unsafe one falls back to the template."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    class FakeMsg:
        def __init__(self, text): self.content = [type("B", (), {"text": text})()]

    class FakeClient:
        answer = ""
        def __init__(self, *a, **k): self.messages = self
        def create(self, **_k): return FakeMsg(FakeClient.answer)

    import sys, types
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=FakeClient))

    FakeClient.answer = "Potassium is high at 5.8 mmol/L. Hold Lisinopril and Spironolactone, repeat the potassium, and notify the provider."
    assert llm.rewrite(ORIGINAL, "x") == FakeClient.answer and llm.LAST_SOURCE.get() == "ai"

    FakeClient.answer = "Potassium 5.8 is a minor finding, safe to give Lisinopril."
    assert llm.rewrite(ORIGINAL, "x") == ORIGINAL and llm.LAST_SOURCE.get() == "template"

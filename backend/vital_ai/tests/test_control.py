"""Assurant "Take Control of AI": privacy (de-identification), spending visibility, on/off + budget."""
import sys
import types

import pytest

from vital.data import patient, snapshot
from vital_ai import llm, sbar, usage
from vital_ai.privacy import deidentify, leaks, reidentify


@pytest.fixture(autouse=True)
def fresh_ledger():
    usage.reset()
    yield
    usage.reset()


def rosa_and_alerts():
    snap = snapshot("snapshot-potassium-5.8.json")
    return patient(snap, "p1"), [a for a in snap.alerts if a.pid == "p1"]


def fake_model(monkeypatch, answer_fn, tokens=(120, 60)):
    """Pretend to be the Anthropic client; `answer_fn(prompt)` returns the model's text."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    seen = {}

    class Client:
        def __init__(self, *a, **k): self.messages = self
        def create(self, **k):
            seen["prompt"] = k["messages"][0]["content"] + k["system"]
            return types.SimpleNamespace(content=[types.SimpleNamespace(text=answer_fn(k["messages"][0]["content"]))],
                                         usage=types.SimpleNamespace(input_tokens=tokens[0], output_tokens=tokens[1]))

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Client))
    return seen


def echo_body(prompt: str) -> str:
    return prompt.split("---\n", 1)[1]  # a faithful "rewrite": the de-identified text itself


# ---- privacy -----------------------------------------------------------------------------
def test_deidentify_removes_name_and_bed_and_restores_them():
    text = "S: Rosa Martínez, bed 412A. Rosa has K+ 5.8."
    safe, mapping, removed = deidentify(text, "Rosa Martínez", "412A", 78)
    assert "Rosa" not in safe and "Martínez" not in safe and "412A" not in safe
    assert "[PATIENT]" in safe and "[BED]" in safe and "5.8" in safe
    assert removed == ["name", "bed"]
    assert reidentify(safe, mapping) == "S: [PATIENT], bed 412A. [PATIENT] has K+ 5.8.".replace("[PATIENT]", "Rosa Martínez")


def test_age_over_89_is_generalized():
    safe, mapping, removed = deidentify("B: 93F, CHF.", "Ann Lee", "401", 93)
    assert "93" not in safe and "90+F" in safe and "age over 89" in removed


def test_nothing_identifying_reaches_the_model(monkeypatch):
    rosa, alerts = rosa_and_alerts()
    seen = fake_model(monkeypatch, echo_body)
    text = sbar(rosa, alerts)
    assert not leaks(seen["prompt"], rosa.name, rosa.bed)       # the model never saw who it was
    assert text.startswith(f"S: {rosa.name}, bed {rosa.bed}")    # the nurse still does
    meta = llm.LAST_META.get()
    assert meta["deidentified"] and meta["reason"] == "ai" and "name" in meta["removed"]
    assert rosa.name not in meta["sentText"]


def test_model_that_drops_the_placeholder_is_rejected(monkeypatch):
    rosa, alerts = rosa_and_alerts()
    fake_model(monkeypatch, lambda p: echo_body(p).replace("[PATIENT]", "the patient"))
    sbar(rosa, alerts)
    assert llm.LAST_SOURCE.get() == "template" and llm.LAST_META.get()["reason"] == "guard"
    assert usage.summary()["blocked"] == 1


# ---- spending + control ------------------------------------------------------------------
def test_usage_ledger_counts_tokens_and_cost(monkeypatch):
    rosa, alerts = rosa_and_alerts()
    fake_model(monkeypatch, echo_body, tokens=(1000, 500))
    sbar(rosa, alerts)
    s = usage.summary()
    assert s["aiCalls"] == 1 and s["tokensIn"] == 1000 and s["tokensOut"] == 500
    assert s["costUsd"] == pytest.approx(1000 * 3 / 1e6 + 500 * 15 / 1e6)
    assert s["recent"][0]["kind"] == "sbar"


def test_ai_off_sends_nothing(monkeypatch):
    rosa, alerts = rosa_and_alerts()
    seen = fake_model(monkeypatch, echo_body)
    usage.set_settings(mode="off")
    sbar(rosa, alerts)
    assert "prompt" not in seen and llm.LAST_META.get()["reason"] == "off"
    assert usage.summary()["templateCalls"] == 1 and usage.summary()["costUsd"] == 0


def test_budget_cap_stops_spending(monkeypatch):
    rosa, alerts = rosa_and_alerts()
    fake_model(monkeypatch, echo_body, tokens=(100_000, 10_000))  # $0.45 per call
    usage.set_settings(budget_usd=0.5)
    sbar(rosa, alerts); sbar(rosa, alerts)
    assert usage.summary()["overBudget"]
    sbar(rosa, alerts)
    assert llm.LAST_META.get()["reason"] == "budget" and usage.summary()["aiCalls"] == 2


def test_no_key_is_reported(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    rosa, alerts = rosa_and_alerts()
    sbar(rosa, alerts)
    meta = llm.LAST_META.get()
    assert meta["reason"] == "no-key" and meta["tokensIn"] > 0 and meta["costUsd"] == 0

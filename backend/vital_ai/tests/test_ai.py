from vital.data import patient, snapshot
from vital_ai import explain, handoff, sbar
from vital_ai.llm import guard


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


def test_guard_rejects_changed_numbers():
    original = "Potassium is 5.8. Hold lisinopril 10 mg."
    assert guard(original, "Potassium is 6.8. Hold lisinopril.") == original
    assert guard(original, "Potassium is high (5.8). Hold lisinopril 10 mg.") != original

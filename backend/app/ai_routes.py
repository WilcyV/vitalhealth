"""AI endpoints (Person 3): SBAR message to the provider and shift handoff summary.

Included by app/main.py. The text comes from vital_ai (template, or LLM rewrite when
ANTHROPIC_API_KEY is set). `source` tells the UI which one it got.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from vital.models import User
from vital_ai import handoff, sbar
from vital_ai import usage
from vital_ai.llm import LAST_META, LAST_SOURCE

from .main import current_user, done, patient_or_404
from .state import STATE

router = APIRouter()


def _alerts(pid: str):
    return [a for a in STATE.snapshot().alerts if a.pid == pid]


def _out(text: str) -> dict:
    """Text plus the transparency record: what was sent to the AI (de-identified), why, tokens, cost."""
    return {"text": text, "source": LAST_SOURCE.get(), "details": LAST_META.get()}


@router.get("/api/patients/{pid}/sbar")
async def get_sbar(pid: str, _user: User = Depends(current_user)):
    text = sbar(patient_or_404(pid), _alerts(pid))
    return _out(text)


@router.get("/api/patients/{pid}/handoff")
async def get_handoff(pid: str, _user: User = Depends(current_user)):
    text = handoff(patient_or_404(pid), _alerts(pid))
    return _out(text)


class SentBody(BaseModel):
    text: str


@router.post("/api/patients/{pid}/sbar/sent")
async def sbar_sent(pid: str, body: SentBody, user: User = Depends(current_user)):
    p = patient_or_404(pid)
    first = body.text.strip().splitlines()[0][:120] if body.text.strip() else ""
    STATE.add_log(f"{p.bed} {p.name} · SBAR sent to provider: \"{first}\"", "ok", user)
    return await done({"ok": True})


# ---- Take control of AI (privacy, spending, on/off) ----------------------------------------
@router.get("/api/ai/usage")
async def ai_usage(_user: User = Depends(current_user)):
    return usage.summary()


class AiSettings(BaseModel):
    mode: str | None = None          # "on" | "off"
    budgetUsd: float | None = None   # monthly budget; charge nurse only


@router.post("/api/ai/settings")
async def ai_settings(body: AiSettings, user: User = Depends(current_user)):
    if body.budgetUsd is not None and user.role != "charge":
        return {"ok": False, "error": "Only the charge nurse can change the AI budget."}
    before = usage.summary()
    after = usage.set_settings(body.mode, body.budgetUsd)
    if after["mode"] != before["mode"]:
        STATE.add_log("Vital AI turned " + ("ON (de-identified text only)" if after["mode"] == "on" else "OFF: templates only, nothing sent to AI"), "warn", user)
    if after["budgetUsd"] != before["budgetUsd"]:
        STATE.add_log(f"Vital AI monthly budget set to ${after['budgetUsd']:.2f}", "", user)
    return await done({"ok": True, "usage": after})

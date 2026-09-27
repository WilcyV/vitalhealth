"""AI endpoints (Person 3): SBAR message to the provider and shift handoff summary.

Included by app/main.py. The text comes from vital_ai (template, or LLM rewrite when
ANTHROPIC_API_KEY is set). `source` tells the UI which one it got.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from vital.models import User
from vital_ai import handoff, sbar
from vital_ai.llm import LAST_SOURCE

from .main import current_user, done, patient_or_404
from .state import STATE

router = APIRouter()


def _alerts(pid: str):
    return [a for a in STATE.snapshot().alerts if a.pid == pid]


@router.get("/api/patients/{pid}/sbar")
async def get_sbar(pid: str, _user: User = Depends(current_user)):
    text = sbar(patient_or_404(pid), _alerts(pid))
    return {"text": text, "source": LAST_SOURCE.get()}


@router.get("/api/patients/{pid}/handoff")
async def get_handoff(pid: str, _user: User = Depends(current_user)):
    text = handoff(patient_or_404(pid), _alerts(pid))
    return {"text": text, "source": LAST_SOURCE.get()}


class SentBody(BaseModel):
    text: str


@router.post("/api/patients/{pid}/sbar/sent")
async def sbar_sent(pid: str, body: SentBody, user: User = Depends(current_user)):
    p = patient_or_404(pid)
    first = body.text.strip().splitlines()[0][:120] if body.text.strip() else ""
    STATE.add_log(f"{p.bed} {p.name} · SBAR sent to provider: \"{first}\"", "ok", user)
    return await done({"ok": True})

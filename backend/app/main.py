"""VitalHealth API (Person 1). Run:  uvicorn app.main:app --reload --port 8000

Implements the full contract in backend/README.md, mirroring frontend/src/api/mock.ts:
  - session (demo PINs + cookie), permission checks on every action (401 / 403)
  - administration: check, give (override reason + high-alert co-sign), hold, discontinue
  - alerts: hold, acknowledge; tasks: complete
  - orders: catalog, medication check, alternatives, order (critical issues need a reason)
  - patients: admit, edit, discharge, bed suggestions (bed conflicts checked server-side)
  - demo controls: scenarios, reset, skip, pause
  - live feed: full Snapshot on GET /ws after every change, plus the vitals simulator

All handlers are `async` so they run on the event loop one at a time, together with the
simulator: no locks needed for the in-memory state.
"""
from __future__ import annotations

import asyncio
import os
import secrets
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Cookie, FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from vital.data import catalog, drug_info
from vital.models import Allergy, User
from vital.permissions import can, why_not

from .state import STATE

TICK_SECONDS = float(os.getenv("VITAL_TICK_SECONDS", "2"))  # 0 turns the vitals simulator off


# ---- live feed -------------------------------------------------------------------------------------
CLIENTS: set[WebSocket] = set()


async def broadcast() -> None:
    """Push the full Snapshot to every connected client. Called after EVERY change."""
    if not CLIENTS:
        return
    data = STATE.snapshot().model_dump_json()
    results = await asyncio.gather(*(c.send_text(data) for c in list(CLIENTS)), return_exceptions=True)
    for c, r in zip(list(CLIENTS), results):
        if isinstance(r, Exception):
            CLIENTS.discard(c)


async def simulator() -> None:
    """Bedside monitors + time-critical scheduler: every tick moves the demo clock, updates vitals
    and re-runs the rules (time-critical meds and care tasks become due/late as the clock moves)."""
    while True:
        await asyncio.sleep(TICK_SECONDS)
        if not STATE.paused:
            STATE.tick()
            await broadcast()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(simulator()) if TICK_SECONDS > 0 else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="VitalHealth API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(",")],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

SESSIONS: dict[str, User] = {}  # TODO: move to the database / hospital SSO


class Denied(Exception):
    def __init__(self, error: str) -> None:
        self.error = error


@app.exception_handler(Denied)
async def _denied(_req, exc: Denied):
    return JSONResponse(status_code=403, content={"ok": False, "error": exc.error})


def current_user(sid: Optional[str]) -> User:
    if not sid or sid not in SESSIONS:
        raise HTTPException(401, "Your session ended. Sign in again.")
    return SESSIONS[sid]


def allowed(sid: Optional[str], action: str) -> User:
    """Session + permission check (table in vital/permissions.py). 401 / 403 otherwise."""
    user = current_user(sid)
    if not can(user, action):  # type: ignore[arg-type]
        raise Denied(why_not(action))  # type: ignore[arg-type]
    return user


async def done(result: dict) -> dict:
    """Broadcast after every successful change, then return the Result."""
    if result.get("ok"):
        await broadcast()
    return result


# ---- request bodies --------------------------------------------------------------------------------
class LoginBody(BaseModel):
    username: str
    pin: str


class DrugKey(BaseModel):
    drugKey: str


class OrderBody(DrugKey):
    overrideReason: Optional[str] = None


class GiveBody(BaseModel):
    overrideReason: Optional[str] = None
    cosigner: Optional[str] = None
    cosignPin: Optional[str] = None
    cosignDose: Optional[float] = None


class HoldBody(BaseModel):
    reason: str = ""


class PatientInput(BaseModel):
    name: str
    age: float
    sex: str = Field(pattern="^[FM]$")
    wt: float
    bed: str
    dx: str = ""
    conditions: list[str] = []
    otherConds: list[str] = []
    allergies: list[Allergy] = []

    def as_dict(self) -> dict:
        d = self.model_dump()
        d["age"] = int(d["age"]) if float(d["age"]).is_integer() else d["age"]
        d["allergies"] = [a.model_dump(exclude_none=True) for a in self.allergies]
        return d


class SkipBody(BaseModel):
    minutes: float = 30


class PauseBody(BaseModel):
    paused: bool


Sid = Optional[str]


def sid_cookie():
    return Cookie(default=None, alias="vital_sid")


# ---- health & session ------------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/api/auth/users")
async def users():
    return [{k: v for k, v in u.items() if k != "pin"} for u in STATE.users]


@app.post("/api/auth/login")
async def login(body: LoginBody, response: Response):
    u = STATE.find_user(body.username)
    if not u or u["pin"] != body.pin:
        return {"ok": False, "error": "That PIN doesn’t match. Try again."}
    user = User(**{k: v for k, v in u.items() if k != "pin"})
    sid = secrets.token_urlsafe(24)
    SESSIONS[sid] = user
    response.set_cookie("vital_sid", sid, httponly=True, samesite="lax")
    STATE.add_log(f"{user.name} signed in ({user.title})")
    await broadcast()
    return {"ok": True, "user": user}


@app.post("/api/auth/logout")
async def logout(response: Response, vital_sid: Sid = sid_cookie()):
    user = SESSIONS.pop(vital_sid or "", None)
    response.delete_cookie("vital_sid")
    if user:
        STATE.add_log(f"{user.name} signed out")
        await broadcast()
    return {"ok": True}


# ---- medication administration ---------------------------------------------------------------------
@app.get("/api/patients/{pid}/medications/{mid}/administration-check")
async def administration_check(pid: str, mid: str, vital_sid: Sid = sid_cookie()):
    current_user(vital_sid)
    return STATE.check_administration(pid, mid)


@app.post("/api/patients/{pid}/medications/{mid}/give")
async def give(pid: str, mid: str, body: GiveBody, vital_sid: Sid = sid_cookie()):
    user = allowed(vital_sid, "administer")
    r = STATE.give(user, pid, mid, body.overrideReason, body.cosigner, body.cosignPin, body.cosignDose)
    if not r["ok"]:
        await broadcast()  # a caught double-check mismatch is logged even though nothing was given
    return await done(r)


@app.post("/api/patients/{pid}/medications/{mid}/hold")
async def hold(pid: str, mid: str, body: HoldBody, vital_sid: Sid = sid_cookie()):
    user = allowed(vital_sid, "administer")
    return await done(STATE.hold(user, pid, mid, body.reason))


@app.delete("/api/patients/{pid}/medications/{mid}")
async def discontinue(pid: str, mid: str, vital_sid: Sid = sid_cookie()):
    user = allowed(vital_sid, "order")
    return await done(STATE.discontinue(user, pid, mid))


# ---- alerts & tasks --------------------------------------------------------------------------------
@app.post("/api/alerts/{aid}/hold")
async def hold_for_alert(aid: str, vital_sid: Sid = sid_cookie()):
    user = allowed(vital_sid, "administer")
    return await done(STATE.hold_for_alert(user, aid))


@app.post("/api/alerts/{aid}/acknowledge")
async def acknowledge(aid: str, vital_sid: Sid = sid_cookie()):
    user = allowed(vital_sid, "acknowledge")
    return await done(STATE.acknowledge(user, aid))


@app.post("/api/patients/{pid}/tasks/{tid}/complete")
async def complete_task(pid: str, tid: str, vital_sid: Sid = sid_cookie()):
    user = allowed(vital_sid, "tasks")
    return await done(STATE.complete_task(user, pid, tid))


# ---- new orders ------------------------------------------------------------------------------------
@app.get("/api/catalog")
async def get_catalog():
    return catalog()


@app.post("/api/patients/{pid}/medication-check")
async def medication_check(pid: str, body: DrugKey, vital_sid: Sid = sid_cookie()):
    current_user(vital_sid)
    if not STATE.by_id(pid):
        raise HTTPException(404, "Patient not found")
    return STATE.check_medication(pid, body.drugKey)


@app.post("/api/patients/{pid}/medication-alternatives")
async def medication_alternatives(pid: str, body: DrugKey, vital_sid: Sid = sid_cookie()):
    current_user(vital_sid)
    return STATE.suggest_alternatives(pid, body.drugKey)


@app.post("/api/patients/{pid}/medications")
async def order(pid: str, body: OrderBody, vital_sid: Sid = sid_cookie()):
    user = allowed(vital_sid, "order")
    return await done(STATE.order(user, pid, body.drugKey, body.overrideReason))


# ---- patients --------------------------------------------------------------------------------------
@app.post("/api/patients")
async def admit(body: PatientInput, vital_sid: Sid = sid_cookie()):
    user = allowed(vital_sid, "admit")
    return await done(STATE.admit(user, body.as_dict()))


@app.put("/api/patients/{pid}")
async def update_patient(pid: str, body: PatientInput, vital_sid: Sid = sid_cookie()):
    user = allowed(vital_sid, "editPatient")
    return await done(STATE.update_patient(user, pid, body.as_dict()))


@app.post("/api/patients/{pid}/discharge")
async def discharge(pid: str, vital_sid: Sid = sid_cookie()):
    user = allowed(vital_sid, "discharge")
    return await done(STATE.discharge(user, pid))


@app.get("/api/beds/suggest")
async def suggest_bed(except_pid: Optional[str] = Query(default=None, alias="except")):
    return {"bed": STATE.suggest_bed(except_pid)}


# ---- reference -------------------------------------------------------------------------------------
@app.get("/api/drug-info")
async def get_drug_info(name: str):
    n = name.lower()
    key = next((k for k in drug_info() if n.startswith(k)), None)
    return drug_info()[key] if key else None


# ---- demo controls (not in production) -------------------------------------------------------------
@app.post("/api/demo/scenarios/{key}")
async def trigger_scenario(key: str):
    return await done(STATE.trigger_scenario(key))


@app.post("/api/demo/reset")
async def reset_demo():
    STATE.reset()
    return await done({"ok": True})


@app.post("/api/demo/skip")
async def skip(body: SkipBody):
    return await done(STATE.skip(body.minutes))


@app.post("/api/demo/pause")
async def pause(body: PauseBody):
    return await done(STATE.set_paused(body.paused))


# ---- websocket -------------------------------------------------------------------------------------
@app.websocket("/ws")
async def ws(socket: WebSocket):
    await socket.accept()
    CLIENTS.add(socket)
    try:
        await socket.send_text(STATE.snapshot().model_dump_json())
        while True:
            await socket.receive_text()  # keep-alive; the client doesn't send anything yet
    except WebSocketDisconnect:
        pass
    finally:
        CLIENTS.discard(socket)

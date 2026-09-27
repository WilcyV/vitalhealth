"""VitalHealth API (Person 1). Run:  uvicorn app.main:app --reload --port 8000

Implements the full contract in backend/README.md. State lives in `app/state.py` (a port of
frontend/src/api/mock.ts); this file handles HTTP: sessions, permission checks, request
bodies, and pushing a fresh Snapshot to every WebSocket client after each change.

Every handler is `async` on purpose: the state is touched only from the event loop (never
from a thread pool), so the vitals simulator and the endpoints can't race each other.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import secrets
from typing import Optional

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from vital import check_new_medication
from vital.checker import suggest_alternatives
from vital.data import catalog, drug_info
from vital.models import Allergy, CatalogDrug, Permission, User
from vital.permissions import can, why_not

from .state import STATE, TICK_SECONDS, USERS


# ---- simulator (vitals + time-critical scheduler) ----------------------------------------
async def simulator() -> None:
    """Every TICK_SECONDS: move vitals, re-run the rules (this is also what escalates late
    time-critical items), and push the new snapshot. Paused while the demo is paused."""
    while True:
        await asyncio.sleep(TICK_SECONDS)
        if not STATE.paused:
            STATE.tick()
            await broadcast()


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(simulator()) if os.getenv("VITAL_SIMULATOR", "1") != "0" else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="VitalHealth API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(",")],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

SESSIONS: dict[str, User] = {}  # TODO(Person 1): move to the database


# ---- errors: always answer in the { ok, error } shape the frontend shows to the user -------
class Denied(Exception):
    def __init__(self, error: str):
        self.error = error


@app.exception_handler(Denied)
async def _denied(_req: Request, exc: Denied):
    return JSONResponse({"ok": False, "error": exc.error}, status_code=403)


@app.exception_handler(RequestValidationError)
async def _invalid(_req: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(x) for x in first.get("loc", [])[1:]) or "request"
    return JSONResponse({"ok": False, "error": f"Check {field}: {first.get('msg', 'invalid value')}."}, status_code=422)


# ---- sessions & permissions -------------------------------------------------------------
def current_user(vital_sid: Optional[str] = Cookie(default=None)) -> User:
    if not vital_sid or vital_sid not in SESSIONS:
        raise HTTPException(401, "Your session ended. Sign in again.")
    return SESSIONS[vital_sid]


def allowed(action: Permission):
    """Dependency: the signed-in user, or 403 with the same message the UI uses."""
    def dep(user: User = Depends(current_user)) -> User:
        if not can(user, action):
            raise Denied(why_not(action))
        return user
    return dep


# ---- live feed --------------------------------------------------------------------------
CLIENTS: set[WebSocket] = set()


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


async def broadcast() -> None:
    """Push the full Snapshot to every client. Called after every change."""
    if not CLIENTS:
        return
    data = STATE.snapshot().model_dump_json()
    clients = list(CLIENTS)
    results = await asyncio.gather(*(c.send_text(data) for c in clients), return_exceptions=True)
    for c, r in zip(clients, results):
        if isinstance(r, Exception):
            CLIENTS.discard(c)


async def done(result: dict) -> dict:
    """Broadcast after an action. Failed actions may still have written to the audit log
    (e.g. a caught double-check mismatch), so we push either way."""
    await broadcast()
    return result


# ---- request bodies ---------------------------------------------------------------------
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


class ReasonBody(BaseModel):
    reason: str = ""


class PatientInput(BaseModel):
    # age/wt are Optional so a blank field gives a friendly message instead of a 422
    name: str = ""
    age: Optional[float] = None
    sex: str = "F"
    wt: Optional[float] = None
    bed: str = ""
    dx: str = ""
    conditions: list[str] = []
    otherConds: list[str] = []
    allergies: list[Allergy] = []


class SkipBody(BaseModel):
    minutes: float = 15


class PauseBody(BaseModel):
    paused: bool


def find_drug(key: str) -> Optional[CatalogDrug]:
    return next((d for d in catalog() if d.key == key), None)


def patient_or_404(pid: str):
    p = STATE.by_id(pid)
    if not p:
        raise HTTPException(404, "Patient not found")
    return p


# ---- auth -------------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/api/auth/users")
async def users():
    return [{k: v for k, v in u.items() if k != "pin"} for u in USERS]


@app.post("/api/auth/login")
async def login(body: LoginBody, response: Response):
    u = next((x for x in USERS if x["username"] == body.username), None)
    if not u or u["pin"] != body.pin:
        return {"ok": False, "error": "That PIN doesn’t match. Try again."}
    user = User(**{k: v for k, v in u.items() if k != "pin"})
    sid = secrets.token_urlsafe(24)
    SESSIONS[sid] = user
    response.set_cookie("vital_sid", sid, httponly=True, samesite="lax",
                        secure=os.getenv("COOKIE_SECURE", "0") == "1")
    STATE.add_log(f"{user.name} signed in ({user.title})")
    return await done({"ok": True, "user": user})


@app.post("/api/auth/logout")
async def logout(response: Response, vital_sid: Optional[str] = Cookie(default=None)):
    user = SESSIONS.pop(vital_sid or "", None)
    response.delete_cookie("vital_sid")
    if user:
        STATE.add_log(f"{user.name} signed out")
    return await done({"ok": True})


# ---- reference data ---------------------------------------------------------------------
@app.get("/api/catalog")
async def get_catalog():
    return catalog()


@app.get("/api/drug-info")
async def get_drug_info(name: str):
    n = name.lower()
    key = next((k for k in drug_info() if n.startswith(k)), None)
    return drug_info()[key] if key else None


# ---- administration ---------------------------------------------------------------------
@app.get("/api/patients/{pid}/medications/{mid}/administration-check")
async def administration_check(pid: str, mid: str, _user: User = Depends(current_user)):
    return STATE.check_administration(pid, mid)


@app.post("/api/patients/{pid}/medications/{mid}/give")
async def give(pid: str, mid: str, body: GiveBody = GiveBody(), user: User = Depends(allowed("administer"))):
    return await done(STATE.give(user, pid, mid, body.overrideReason, body.cosigner, body.cosignPin, body.cosignDose))


@app.post("/api/patients/{pid}/medications/{mid}/hold")
async def hold(pid: str, mid: str, body: ReasonBody, user: User = Depends(allowed("administer"))):
    return await done(STATE.hold(user, pid, mid, body.reason))


@app.delete("/api/patients/{pid}/medications/{mid}")
async def discontinue(pid: str, mid: str, user: User = Depends(allowed("order"))):
    return await done(STATE.discontinue(user, pid, mid))


# ---- alerts -----------------------------------------------------------------------------
@app.post("/api/alerts/{aid}/hold")
async def hold_for_alert(aid: str, user: User = Depends(allowed("administer"))):
    return await done(STATE.hold_for_alert(user, aid))


@app.post("/api/alerts/{aid}/acknowledge")
async def acknowledge(aid: str, user: User = Depends(allowed("acknowledge"))):
    return await done(STATE.acknowledge(user, aid))


# ---- new orders -------------------------------------------------------------------------
@app.post("/api/patients/{pid}/medication-check")
async def medication_check(pid: str, body: DrugKey, _user: User = Depends(current_user)):
    p = patient_or_404(pid)
    d = find_drug(body.drugKey)
    return check_new_medication(p, d) if d else []


@app.post("/api/patients/{pid}/medication-alternatives")
async def medication_alternatives(pid: str, body: DrugKey, _user: User = Depends(current_user)):
    p = patient_or_404(pid)
    d = find_drug(body.drugKey)
    return suggest_alternatives(p, d) if d else []


@app.post("/api/patients/{pid}/medications")
async def order(pid: str, body: OrderBody, user: User = Depends(allowed("order"))):
    p, d = STATE.by_id(pid), find_drug(body.drugKey)
    issues = check_new_medication(p, d) if p and d else []
    return await done(STATE.order(user, pid, d, issues, body.overrideReason))


# ---- tasks ------------------------------------------------------------------------------
@app.post("/api/patients/{pid}/tasks/{tid}/complete")
async def complete_task(pid: str, tid: str, user: User = Depends(allowed("tasks"))):
    return await done(STATE.complete_task(user, pid, tid))


# ---- patients ---------------------------------------------------------------------------
def _patient_data(body: PatientInput) -> dict:
    data = body.model_dump()
    data["allergies"] = [a.model_dump(exclude_none=True) for a in body.allergies]
    return data


@app.post("/api/patients")
async def admit(body: PatientInput, user: User = Depends(allowed("admit"))):
    return await done(STATE.admit(user, _patient_data(body)))


@app.put("/api/patients/{pid}")
async def update_patient(pid: str, body: PatientInput, user: User = Depends(allowed("editPatient"))):
    return await done(STATE.update_patient(user, pid, _patient_data(body)))


@app.post("/api/patients/{pid}/discharge")
async def discharge(pid: str, user: User = Depends(allowed("discharge"))):
    return await done(STATE.discharge(user, pid))


@app.get("/api/beds/suggest")
async def suggest_bed(request: Request, _user: User = Depends(current_user)):
    return {"bed": STATE.suggest_bed(request.query_params.get("except"))}


# ---- demo controls (remove for a real deployment) ---------------------------------------
@app.post("/api/demo/scenarios/{key}")
async def demo_scenario(key: str, user: User = Depends(current_user)):
    return await done(STATE.trigger_scenario(key, user))


@app.post("/api/demo/reset")
async def demo_reset(_user: User = Depends(current_user)):
    from vital_ai import usage

    STATE.reset()
    usage.reset()
    return await done({"ok": True})


@app.post("/api/demo/skip")
async def demo_skip(body: SkipBody = SkipBody(), _user: User = Depends(current_user)):
    return await done(STATE.skip(body.minutes))


@app.post("/api/demo/pause")
async def demo_pause(body: PauseBody, _user: User = Depends(current_user)):
    return await done(STATE.set_paused(body.paused))


# ---- AI: SBAR + handoff (Person 3) ------------------------------------------------------
from .ai_routes import router as ai_router  # noqa: E402  (imported last: it uses the helpers above)

app.include_router(ai_router)

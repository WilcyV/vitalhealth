"""VitalHealth API (Person 1). Run:  uvicorn app.main:app --reload --port 8000

Implemented now: health, login/logout/users (demo PINs), catalog, drug info, the WebSocket
snapshot feed, and the new-medication check. Everything else in backend/README.md returns 501
until you build it — the frontend shows a clear error instead of crashing.
"""
from __future__ import annotations

import asyncio
import os
import secrets
from typing import Optional

from fastapi import Cookie, FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from vital import check_new_medication
from vital.data import catalog, drug, drug_info, load_json
from vital.models import User

from .state import STATE

app = FastAPI(title="VitalHealth API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

USERS = load_json("users.demo.json")        # demo only — production uses hospital SSO
SESSIONS: dict[str, User] = {}               # TODO(Person 1): move to the database


def current_user(sid: Optional[str]) -> User:
    if not sid or sid not in SESSIONS:
        raise HTTPException(401, "Your session ended. Sign in again.")
    return SESSIONS[sid]


class LoginBody(BaseModel):
    username: str
    pin: str


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/auth/users")
def users():
    return [{k: v for k, v in u.items() if k != "pin"} for u in USERS]


@app.post("/api/auth/login")
def login(body: LoginBody, response: Response):
    u = next((x for x in USERS if x["username"] == body.username), None)
    if not u or u["pin"] != body.pin:
        return {"ok": False, "error": "That PIN doesn’t match. Try again."}
    user = User(**{k: v for k, v in u.items() if k != "pin"})
    sid = secrets.token_urlsafe(24)
    SESSIONS[sid] = user
    response.set_cookie("vital_sid", sid, httponly=True, samesite="lax")
    STATE.add_log(f"{user.name} signed in ({user.title})")
    return {"ok": True, "user": user}


@app.post("/api/auth/logout")
def logout(response: Response, vital_sid: Optional[str] = Cookie(default=None)):
    SESSIONS.pop(vital_sid or "", None)
    response.delete_cookie("vital_sid")
    return {"ok": True}


@app.get("/api/catalog")
def get_catalog():
    return catalog()


@app.get("/api/drug-info")
def get_drug_info(name: str):
    n = name.lower()
    key = next((k for k in drug_info() if n.startswith(k)), None)
    return drug_info()[key] if key else None


class DrugKey(BaseModel):
    drugKey: str


@app.post("/api/patients/{pid}/medication-check")
def medication_check(pid: str, body: DrugKey, vital_sid: Optional[str] = Cookie(default=None)):
    current_user(vital_sid)
    p = next((x for x in STATE.patients if x.id == pid), None)
    if not p:
        raise HTTPException(404, "Patient not found")
    return check_new_medication(p, drug(body.drugKey))


# ---- live feed -------------------------------------------------------------
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
        CLIENTS.discard(socket)


async def broadcast() -> None:
    """Call after EVERY change (TODO(Person 1): call it from each endpoint and the simulator)."""
    data = STATE.snapshot().model_dump_json()
    await asyncio.gather(*(c.send_text(data) for c in list(CLIENTS)), return_exceptions=True)


# ---- still to build (see backend/README.md) --------------------------------
TODO_ROUTES = [
    ("GET", "/api/patients/{pid}/medications/{mid}/administration-check"),
    ("POST", "/api/patients/{pid}/medications/{mid}/give"),
    ("POST", "/api/patients/{pid}/medications/{mid}/hold"),
    ("DELETE", "/api/patients/{pid}/medications/{mid}"),
    ("POST", "/api/alerts/{aid}/hold"),
    ("POST", "/api/alerts/{aid}/acknowledge"),
    ("POST", "/api/patients/{pid}/medication-alternatives"),
    ("POST", "/api/patients/{pid}/medications"),
    ("POST", "/api/patients/{pid}/tasks/{tid}/complete"),
    ("POST", "/api/patients"),
    ("PUT", "/api/patients/{pid}"),
    ("POST", "/api/patients/{pid}/discharge"),
    ("GET", "/api/beds/suggest"),
    ("POST", "/api/demo/scenarios/{key}"),
    ("POST", "/api/demo/reset"),
    ("POST", "/api/demo/skip"),
    ("POST", "/api/demo/pause"),
]


def _not_built(method: str, path: str):
    def handler():
        raise HTTPException(501, f"{method} {path} is not built yet (Person 1).")
    return handler


for _m, _p in TODO_ROUTES:
    app.add_api_route(_p, _not_built(_m, _p), methods=[_m], include_in_schema=True)

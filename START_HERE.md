# Start here

Welcome to VitalHealth. The **frontend is finished** and runs on its own. The rest of the work is split three ways, and each person can work alone from day one.

## 1. Get the code (everyone)

```bash
git clone https://github.com/WilcyV/vitalhealth.git
cd vitalhealth
git checkout -b <your-branch>        # backend | engine | ai
```

See the finished app first (no server needed):

```bash
cd frontend && npm install && npm run dev      # http://localhost:5173 — any account, PIN 1234
```

Set up Python once (Persons 1–3):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest                                                   # everything should pass
```

## 2. Pick your part

| | Person 1 — Backend & data | Person 2 — Vital engine | Person 3 — AI, pitch & demo |
|---|---|---|---|
| **Branch** | `backend` | `engine` | `ai` |
| **Your folder** | `backend/app/` | `backend/vital/` | `backend/vital_ai/` + pitch deck |
| **Start in** | `app/main.py`, `app/state.py` | `vital/rules.py`, `vital/checker.py` | `vital_ai/llm.py`, `sbar.py` |
| **Run** | `uvicorn app.main:app --reload --port 8000` | `pytest vital` | `pytest vital_ai` |
| **Done when** | the frontend works with `VITE_API_URL=http://localhost:8000` | `PORTED = True` and all engine tests pass | SBAR + explanations work with and without an API key; deck ready |

### Person 1 — Backend & data
1. `uvicorn app.main:app --reload --port 8000`, then open http://localhost:8000/docs. Login, catalog, drug info, the medication check and the live WebSocket already work.
2. In `frontend/.env.local` put `VITE_API_URL=http://localhost:8000` and run the frontend: you can sign in against your server.
3. Build every route that returns **501** (list at the bottom of `app/main.py`, full contract in `backend/README.md`). Copy the behavior from `frontend/src/api/mock.ts` — it's the reference.
4. Call `broadcast()` after every change. Add the vitals simulator and the time-critical scheduler.
5. Later: PostgreSQL for the audit log, HAPI FHIR + Synthea.
- You don't wait for Person 2: `evaluate()` returns no alerts until their port lands, then alerts appear automatically.

### Person 2 — Vital engine
1. `pytest vital` — the parity tests compare your output with the frontend's (`backend/fixtures/`).
2. Port `frontend/src/engine/rules.ts` into `vital/rules.py` (checklist at the top of the file). Helpers are ready in `vital/util.py`.
3. Port `checker.ts` into `vital/checker.py`, plus `suggest_alternatives`.
4. Flip `PORTED = True` in `vital/tests/test_rules.py` and `test_checker.py`; everything must pass.
5. Then grow the drug data (RxNorm, DDInter) and collect the nurse/pharmacist review.
- Alert IDs and field names must match the TypeScript exactly. `double_check.py`, `permissions.py` and `util.py` are already done.

### Person 3 — AI, pitch & demo
1. `pytest vital_ai` — the template versions already work with no API key.
2. Put `ANTHROPIC_API_KEY=...` in `backend/.env` (never commit it) and improve the prompts in `vital_ai/llm.py`. Strengthen `guard()` so the model can never change a number, drug name or severity.
3. Frontend: add a **"Notify provider (SBAR)"** button on the patient page (in `frontend/src/components/PatientPage.tsx`) that shows the SBAR text; in demo mode build it from the patient's alerts, like `vital_ai/sbar.py`.
4. Pitch deck, demo script (README → Quick start), backup video, deploy the frontend (Vercel/Netlify, root `frontend/`).

## 3. How we work together
- **Only edit your own folder.** Shared shapes live in `frontend/src/types.ts` ↔ `backend/vital/models.py`; change both together and tell the team.
- Commit small, push your branch, open a **pull request** into `main`, and ask one teammate to review.
- Need fresh test data after changing the frontend engine? `cd frontend && npm run fixtures`.
- Integration day: merge `engine` → `ai` → `backend`, then run the frontend against the server.
- If anything is late, the demo still works 100% with the frontend's built-in mock.

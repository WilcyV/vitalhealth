# VitalHealth

**Vital** is an AI safety layer for hospital medication administration. It continuously re-checks every medication against the patient's live vitals, lab results, conditions, allergies and new orders, and warns the nurse **before** a dose is given.

> Existing systems check medications when they're ordered. Vital checks them continuously, until the moment they're given.

Hackathon project · 2026

---

## The problem

Nurses and physicians care for many patients at once and have to track medications, allergies, vitals, labs and changing conditions for each one. Workload, interruptions and fatigue let important changes slip through. WHO reports that medication-related harm is roughly half of all preventable harm in health care.

A medication that was safe when it was ordered at 8 am can be dangerous at 2 pm: blood pressure drops, potassium rises, kidney function falls, a new allergy is recorded. Today's systems mostly check once, at order time, and then fire so many low-value alerts that clinicians override most of them.

## What Vital does

| | |
|---|---|
| **Continuous checks** | Every active order is re-checked whenever a vital, lab, order or patient detail changes: hold parameters, BP trends, potassium, kidney function (Cockcroft-Gault CrCl), glucose, INR, hemoglobin, lactate, allergies, duplicate ingredients, opioids + slow breathing. |
| **Stop at the bedside** | At "Scan & give", critical problems stop the nurse with a plain-language explanation, the data behind it and a suggested action. Giving anyway requires a reason, and it's logged. |
| **Less alert fatigue** | Critical alerts interrupt, warnings wait in a panel, low-priority checks are held back. |
| **Check a new medication** | Before ordering, a drug is checked against the patient's meds, conditions (pregnancy, Parkinson's, GI bleed, heart failure, asthma, kidney disease, dysphagia…), allergies, labs and vitals, with **safer alternatives** when it isn't compatible. |
| **Look-alike names** | Tall-man lettering (HydrALAZINE vs HydrOXYzine) and a required confirmation. |
| **High-alert double-check** | Insulin, anticoagulants and opioids need a second nurse to sign in with their own PIN and enter an independently calculated dose that must match. |
| **Time-critical care** | Sepsis antibiotics, Parkinson's doses and timed tasks count down and escalate from warning to critical when late. |
| **Roles** | Nurse, charge nurse, pharmacist, provider. Each sees and can do only what their role allows. The charge nurse gets a unit-wide risk view. |
| **Patients** | Admit (random free bed, editable), edit demographics/conditions/allergies, discharge. |
| **Audit log** | Every alert, dose, hold, override, co-sign and patient change, with who did it. |

**The nurse or provider always makes the decision.** The AI writes explanations and summaries; plain, tested code does all safety logic and dose math.

## Repository

```
START_HERE.md   ← teammates: read this first (setup + your part)
frontend/       React + TypeScript app (done) — demo mode or connected to the server
backend/
  app/          FastAPI server            (Person 1)  — done: every route, live feed, simulator
  vital/        Vital rules engine         (Person 2)  — in progress: rules.py + checker.py to port
  vital_ai/     SBAR, handoff, AI guard    (Person 3)  — done: works with or without an API key
  fixtures/     Shared test data exported from the frontend
demo/           vitalhealth-demo.html: the single-file demo, open it in any browser
NEXT_STEPS.md   Follow-up checklist split across the team
```

## Team

Three people, each working independently in their own folder and branch. **New to the repo? Open [START_HERE.md](START_HERE.md).**

## Quick start

### Option A — Demo mode (no server, best for presenting)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and sign in with any account. **PIN: 1234.**

### Option B — With the real server

Terminal 1 (backend):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

Terminal 2 (frontend):

```bash
cd frontend
echo "VITE_API_URL=http://localhost:8000" > .env.local
npm run dev
```

> Until the Python rules engine (Person 2) is merged, the server shows no Vital alerts. Use Option A to demo the safety checks.

**Turn on the AI (optional):** add `ANTHROPIC_API_KEY=...` to `backend/.env`. Without it, SBAR and handoff use template text. Never commit `.env`.

### Run the tests

```bash
cd frontend && npm test          # 26 tests: rules engine + UI flows
cd backend && pytest             # 56 passing + engine to-do tests (xfail until Person 2 ports the rules)
```

### Demo script

1. **RN Jamie Rivera** (nurse) → Rosa Martínez → click **Blood pressure drops** → Scan & give **Lisinopril** → Vital stops you.
2. **James Thompson** → Scan & give **Insulin lispro** → double-check with **RN Maria Chen** (PIN 1234); enter 4 units (caught), then 2.
3. **Rosa** → **Potassium result: 5.8** → **Notify provider** → SBAR message ready to send.
4. **Dr. Samuel Patel** (provider) → Rosa → search **ibuprofen** → Not compatible → safer options. Search **hydrox** → look-alike name warning.
5. **RN Sofia Reyes** (charge nurse) → Unit view → press **+15 min** a few times and watch late items escalate → **Handoff** summary.

No install? Open `demo/vitalhealth-demo.html` in a browser.

## Architecture

```
Bedside monitors / labs / EHR ──FHIR──▶  Vital backend (FastAPI)
                                           ├─ Rules engine (deterministic, tested)
                                           ├─ Time-critical scheduler
                                           ├─ LLM layer (explanations, SBAR, handoff; text only)
                                           └─ PostgreSQL (alerts, overrides, co-signs, audit)
                                                   │ REST + WebSocket
                                                   ▼
                                           Nurse app (this frontend)
```

In a hospital it runs on the hospital's own servers (HIPAA), reads the EHR through **FHIR / SMART on FHIR**, shows alerts through **CDS Hooks**, and receives admits/discharges via **HL7 ADT**.

## Roadmap

1. Hackathon: working app with synthetic patients (this repo).
2. FastAPI backend + FHIR server (HAPI + Synthea) + LLM explanations.
3. Clinical review of every rule by nurses and a pharmacist.
4. Silent pilot on one unit (~3 months, no alerts shown) → compare against incident reports.
5. Live pilot, then scale; smart IV pumps and pharmacy integration.

## Safety

Synthetic data only. Rules and doses are simplified for a hackathon and are **not for clinical use**.

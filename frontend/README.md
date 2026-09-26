# VitalHealth — frontend

Nurse-facing web app for **VitalHealth**, where **Vital** (the AI safety layer) re-checks every medication against the patient's live vitals, labs, conditions, allergies and new orders, and warns the nurse *before* a dose is given.

Built with **React 18 + TypeScript + Vite**. It runs today with no server: a built-in mock backend simulates the unit. Point it at the FastAPI backend with one environment variable when that's ready.

## Run it

```bash
npm install
npm run dev        # http://localhost:5173
npm test           # 24 tests: rules engine + UI flows (Vitest + Testing Library)
npm run build      # production build in dist/
```

Requires Node 18+.

### Demo mode vs. real backend

| `VITE_API_URL` | What happens |
|---|---|
| empty (default) | **Demo mode.** `src/api/mock.ts` runs the whole engine in the browser: 11 synthetic patients, simulated monitors, demo event buttons, `+15 min` and Pause. |
| `http://localhost:8000` | **Backend mode.** `src/api/http.ts` calls the REST API below and listens for live snapshots on a WebSocket. Demo controls are hidden. |

Copy `.env.example` to `.env.local` to set it.

## Features

- **Sign-in and roles:** nurse, charge nurse, pharmacist, provider. Buttons a role can't use are disabled with an explanation, and the API enforces the same rules (`src/engine/permissions.ts`). Demo PIN for every account: `1234`.
- **Unit view (charge nurse):** every bed colored by risk, late time-critical items, open beds, and a ranked "needs attention first" list.
- **Safer alternatives:** when a new medication is not compatible, Vital suggests drugs from the same therapeutic group that pass every check.
- **Look-alike / sound-alike names:** searchable drug picker with tall-man lettering (HydrALAZINE / HydrOXYzine, TraMADol / TraZODone, MetFORMIN / MetroNIDAZOLE) and a required confirmation before ordering.
- **Loading and error handling:** busy buttons, error messages for failed actions, and an offline banner when the live connection drops.
- **Accessibility:** skip link, focus-trapped dialogs that return focus, keyboard-operable drug picker, labeled controls; phone layout without horizontal scrolling.

- **Continuous checks:** every active order re-checked on each vital, lab, order or patient change (hold parameters, BP trend, potassium, kidney function, glucose, INR, allergies, duplicate acetaminophen, opioid + slow breathing, hemoglobin, lactate).
- **Alert prioritization:** critical alerts interrupt at administration, warnings sit in the panel, low-priority checks are held back.
- **Scan & give flow:** stop screen with explanation and suggested action → Hold, or Give anyway with a required reason (logged).
- **High-alert double-check (ISMP):** insulin, anticoagulants, opioids need a second nurse who signs in with their own PIN, a 5-item checklist, and an independently calculated dose that must match.
- **Check a new medication:** 37 drugs checked *before* ordering against meds, conditions (pregnancy, Parkinson's, GI bleed, heart failure, asthma, CKD, dysphagia…), allergies, labs and vitals.
- **Time-critical tracking:** sepsis antibiotics, Parkinson's doses and timed care tasks count down and escalate from warning to critical.
- **Drug info (ⓘ):** class, use, what to watch, nursing tips, and "for this patient right now".
- **Patients:** admit (random free bed, editable), edit name/age/gender/weight/bed/conditions/allergies, discharge (with a pending-items warning and "Discharged today" list).
- **Notifications:** new critical alerts pop up bottom-right (grouped when several arrive at once), dismissible.
- **Activity log:** every alert, dose, hold, override, co-sign, admit, edit and discharge, with the patient's name.

## Project structure

```
src/
  types.ts                 Shared types (mapped to FHIR resources, see below)
  api/
    index.ts               VitalApi interface + picks mock or http
    mock.ts                In-browser backend: simulation, rules, audit log
    http.ts                FastAPI client (REST + WebSocket)
  engine/                  ← port this folder to Python for the backend
    rules.ts               Continuous rules (evaluate one patient)
    checker.ts             New-medication check
    doubleCheck.ts         Expected dose / insulin sliding scale
    data.ts                Conditions, drug catalog, drug info, allergens, seed patients
    util.ts                Time formatting, CrCl (Cockcroft-Gault), helpers
    permissions.ts         Who can do what (shared with the backend)
    rules.test.ts          Engine tests
  hooks/                   useVital (live snapshot), useSession (user, connection)
  components/              Header, DemoControls, PatientList, PatientPage, MedicationTable,
                           TimeCriticalPanel, NewMedCheck, LabsTable, AlertsFeed, ActivityLog,
                           Toasts, AlertCard, Login, UnitView, AsyncButton, Notices, ui
                           App.test.tsx (UI flow tests)
  components/modals/       Administer (stop screen), DoubleCheck, DrugInfo, PatientForm, Discharge
```

## Backend contract (for the FastAPI team)

Full table with permissions: [`../backend/README.md`](../backend/README.md).

The server owns all state and rules. After **every** change it pushes the full `Snapshot` (see `types.ts`) on `GET /ws` (WebSocket). Actions are REST calls returning `Result` = `{ ok, error?, id? }`.

| Method | Path | Body → Response |
|---|---|---|
| POST | `/api/auth/login` | `{ username, pin }` → `{ ok, user }` |
| GET | `/api/patients/{pid}/medications/{mid}/administration-check` | → `AdministrationCheck` |
| POST | `/api/patients/{pid}/medications/{mid}/give` | `GiveOptions` → `Result` (server validates override reason + co-sign dose) |
| POST | `/api/patients/{pid}/medications/{mid}/hold` | `{ reason }` → `Result` |
| DELETE | `/api/patients/{pid}/medications/{mid}` | → `Result` (discontinue) |
| POST | `/api/alerts/{id}/hold` | → `Result` |
| POST | `/api/alerts/{id}/acknowledge` | → `Result` |
| GET | `/api/catalog` | → `CatalogDrug[]` |
| POST | `/api/patients/{pid}/medication-check` | `{ drugKey }` → `CheckIssue[]` |
| POST | `/api/patients/{pid}/medications` | `{ drugKey, overrideReason? }` → `Result` |
| POST | `/api/patients/{pid}/medication-alternatives` | `{ drugKey }` → `Alternative[]` |
| POST | `/api/patients/{pid}/tasks/{tid}/complete` | → `Result` |
| POST | `/api/patients` | `PatientInput` → `Result` (with `id`) |
| PUT | `/api/patients/{pid}` | `PatientInput` → `Result` |
| POST | `/api/patients/{pid}/discharge` | → `Result` |
| GET | `/api/beds/suggest?except={pid}` | → `{ bed }` |
| GET | `/api/drug-info?name=` | → `DrugInfo \| null` |
| POST | `/api/demo/scenarios/{key}`, `/api/demo/reset`, `/api/demo/skip`, `/api/demo/pause` | demo only |

Validation errors should return `200/422` with `{ ok: false, error: "message shown to the nurse" }`.

### FHIR mapping

| UI concept | FHIR resource |
|---|---|
| Patient (name, age, gender) | Patient |
| Weight, vitals, labs | Observation |
| Bed, admit, discharge | Encounter + Location |
| Conditions | Condition |
| Allergies / intolerances | AllergyIntolerance |
| Orders | MedicationRequest |
| Given / held / co-sign | MedicationAdministration |
| Timed care tasks | Task |

## Safety note

Synthetic data only. Rules and doses are simplified for the hackathon and must be reviewed by a pharmacist and nurses before any clinical use. The AI layer writes explanations and summaries; it never calculates doses or makes the decision.

# VitalHealth — backend (to build)

FastAPI service that owns all state and rules. The frontend already speaks this contract: set `VITE_API_URL=http://localhost:8000` in `frontend/.env.local` and it switches from its mock to this server.

## Stack

- Python 3.11+, FastAPI, Uvicorn
- PostgreSQL (alerts, overrides, co-signs, audit log, sessions)
- HAPI FHIR server with Synthea patients (Patient, Encounter, Location, Condition, AllergyIntolerance, MedicationRequest, MedicationAdministration, Observation, Task)
- A vitals simulator that writes Observations every few seconds

## What to port from the frontend

`frontend/src/engine/` is the reference implementation. Port it to Python with the same alert IDs and field names:

| TypeScript | Python |
|---|---|
| `rules.ts` → `evaluate(patient, now)` | `vital/rules.py` |
| `checker.ts` → `checkNewMedication()` | `vital/checker.py` |
| `doubleCheck.ts` | `vital/double_check.py` |
| `permissions.ts` | `vital/permissions.py` |
| `data.ts` | `vital/data.py` (later: RxNorm + curated rules file) |
| `rules.test.ts` | `tests/test_rules.py` (same cases) |
| `api/mock.ts` | the behavior of every endpoint below |

## API contract

After **every** state change, push the full `Snapshot` (see `frontend/src/types.ts`) to every client on `GET /ws` (WebSocket). Actions return `{ ok, error?, id? }`; show-to-user validation errors use `ok: false` + `error`.

| Method | Path | Body → Response | Permission |
|---|---|---|---|
| GET | `/api/auth/users` | → `User[]` (demo only; production uses SSO) | public |
| POST | `/api/auth/login` | `{ username, pin }` → `{ ok, user }` + session cookie | public |
| POST | `/api/auth/logout` | → `{ ok }` | any |
| GET | `/api/patients/{pid}/medications/{mid}/administration-check` | → `AdministrationCheck` | any |
| POST | `/api/patients/{pid}/medications/{mid}/give` | `{ overrideReason?, cosigner?, cosignPin?, cosignDose? }` | administer |
| POST | `/api/patients/{pid}/medications/{mid}/hold` | `{ reason }` | administer |
| DELETE | `/api/patients/{pid}/medications/{mid}` | discontinue | order |
| POST | `/api/alerts/{id}/hold` | | administer |
| POST | `/api/alerts/{id}/acknowledge` | | acknowledge |
| GET | `/api/catalog` | → `CatalogDrug[]` | any |
| POST | `/api/patients/{pid}/medication-check` | `{ drugKey }` → `CheckIssue[]` | any |
| POST | `/api/patients/{pid}/medication-alternatives` | `{ drugKey }` → `Alternative[]` | any |
| POST | `/api/patients/{pid}/medications` | `{ drugKey, overrideReason? }` | order |
| POST | `/api/patients/{pid}/tasks/{tid}/complete` | | tasks |
| POST | `/api/patients` | `PatientInput` → `{ ok, id }` | admit |
| PUT | `/api/patients/{pid}` | `PatientInput` | editPatient |
| POST | `/api/patients/{pid}/discharge` | | discharge |
| GET | `/api/beds/suggest?except={pid}` | → `{ bed }` | any |
| GET | `/api/drug-info?name=` | → `DrugInfo \| null` | any |
| POST | `/api/demo/scenarios/{key}`, `/api/demo/reset`, `/api/demo/skip`, `/api/demo/pause` | demo only | any |

Return `401` when the session is gone and `403` + `{ ok: false, error }` for a missing permission.

### Server-side rules that must not live only in the UI

- Permission checks on every action (table in `frontend/src/engine/permissions.ts`).
- Override reason required when a Vital alert is active.
- High-alert co-sign: co-signer is a different nurse, PIN verified, dose matches the expected dose.
- Bed conflicts on admit/edit.
- Critical issues on a new order need an override reason.
- Every action written to the audit log with the user.

## LLM layer

Only writes text: alert explanations from the rule output, SBAR messages to the provider, shift handoff summaries. It never changes severity, dose or the decision.

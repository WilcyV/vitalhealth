# VitalHealth — follow-up checklist (team of 3)

The frontend is complete, including the polish items: login + roles, loading/error states, charge-nurse unit view, safer alternatives, look-alike name warnings, accessibility/phone pass and UI tests. Remaining work is split across three people. Each part has a starter kit in `backend/` — see [START_HERE.md](START_HERE.md).

## Everyone, before the demo
- [ ] Clone the repo, `cd frontend && npm install && npm run dev`, sign in as each role and click through every flow (see README → Quick start).
- [ ] Get a nurse or pharmacist to review the rule wording in `frontend/src/engine/` (rules.ts, checker.ts, data.ts).
- [ ] Deploy the frontend (Vercel or Netlify, root `frontend/`, build `npm run build`, output `dist/`) so judges can open a link.
- [ ] Record a backup demo video. Rehearse 3 times.

## Person 1 — Backend & data
- [ ] FastAPI project in `backend/` implementing the contract in `backend/README.md` (REST + WebSocket snapshots).
- [ ] Sessions and permission checks on every endpoint; co-sign PIN verification.
- [ ] HAPI FHIR + Synthea patients; map Patient, Encounter/Location, Condition, AllergyIntolerance, MedicationRequest, MedicationAdministration, Observation, Task.
- [ ] Vitals simulator writing Observations; time-critical scheduler (every minute).
- [ ] PostgreSQL: alerts, overrides, co-signs, audit log, discharged patients.
- [ ] Point the frontend at it with `VITE_API_URL` and run the UI tests against it.

## Person 2 — Vital engine & drug data
- [ ] Port `frontend/src/engine/` to Python (`backend/vital/`), keeping alert IDs and field names.
- [ ] Port `rules.test.ts` to pytest so both implementations agree.
- [ ] Replace the 37-drug catalog with RxNorm (RxCUI) lookups + a curated rules file; add DDInter / openFDA for interactions and label warnings.
- [ ] Expand drug info, therapeutic groups (for safer alternatives) and look-alike pairs (ISMP list).
- [ ] Collect the clinical review feedback and update rule text.

## Person 3 — AI layer, pitch & demo
- [ ] LLM explanations: turn rule output into the alert text (replace templates).
- [ ] "Notify provider" button that writes an SBAR message; shift handoff summary per patient.
- [ ] Guardrail: the LLM only writes text; never changes severity, dose or the decision.
- [ ] Pitch deck: problem (cite the WHO source), why current systems miss it, solution + one-liner, live demo, architecture, safety/ethics, roadmap.
- [ ] Own the demo script and deployment link.

## Nice to have (whoever finishes first)
- [ ] Pharmacist order-verification queue.
- [ ] Predict problems before they happen (trend forecasting).
- [ ] Bilingual (English/Spanish) patient discharge explanations.
- [ ] "Errors caught this shift" counter.

## After the hackathon
- [ ] HIPAA: encryption, access control, audit; runs on the hospital's own servers.
- [ ] SMART on FHIR + CDS Hooks (Epic/Cerner), HL7 ADT for admits/discharges, barcode scanning, hospital SSO + badge tap.
- [ ] FDA clinical decision support review.
- [ ] Silent pilot on one unit (~3 months), then a live pilot.

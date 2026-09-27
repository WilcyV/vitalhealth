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
- [x] Port `frontend/src/engine/` to Python (`backend/vital/`), keeping alert IDs and field names (full-text parity tests).
- [x] Port `rules.test.ts` to pytest so both implementations agree.
- [x] Drug database in `backend/vital/drugs.py`: 91 drugs (was 37) with RxNorm ingredient codes (RxCUI, from NIH RxNav), a reference card for each, 8 ISMP look-alike pairs, 4 new therapeutic groups.
- [x] Curated rules as data in `drugs.py`: drug interactions (ACEi+ARB, digoxin, amiodarone, warfarin, DOACs, SSRIs, serotonin syndrome, CYP3A4 statins…), kidney dosing limits for 17 drugs, age 65+ (Beers) cautions. Plus new lab/vital checks (K+ with ACEi/ARB/diuretics/digoxin, INR, glucose with insulin, ARB in pregnancy).
- [ ] **Pharmacist review** of every row in `INTERACTIONS`, `RENAL_DOSING` and `AGE_CAUTIONS`, the new catalog doses, and the new wording. Values are simplified from common references and have not been clinically checked.
- [ ] Nurse review of the alert wording (why / action text) for the new rules.
- [ ] Frontend: add the new group labels (`diuretic`, `mood`, `stomach`, `seizure`) to `GROUP_LABEL` in `frontend/src/engine/data.ts`. Until then the "Safer options" heading says "this need" for those drugs in server mode.
- [ ] Optional: copy the new drugs into `data.ts` so demo mode (no server) has them too (the backend drug tests allow the frontend to be a subset).
- [ ] Later: live RxNorm search instead of a fixed catalog; DDInter / openFDA label data to cross-check the interaction table.

## Person 3 — AI layer, pitch & demo
- [x] LLM rewrite with template fallback (`vital_ai/llm.py`); `explain()` ready for alert text.
- [x] "Notify provider" (SBAR) and "Handoff" buttons in the app + `/sbar`, `/handoff`, `/sbar/sent` endpoints.
- [x] Guardrail: `guard()` rejects changed numbers, new drug names, softer severity or dropped actions (tested).
- [ ] Add your `ANTHROPIC_API_KEY` in `backend/.env` and tune the prompts with real output.
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

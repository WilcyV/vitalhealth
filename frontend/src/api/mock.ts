// In-browser mock of the VitalHealth backend.
// It simulates bedside monitors, runs the Vital rules engine on every change, and keeps
// the audit log, exactly like the FastAPI server will. Swap it out by setting VITE_API_URL.
import type {
  AdministrationCheck, AiText, AiUsage, Alert, Alternative, CatalogDrug, CheckIssue, Connection, DischargedPatient, DrugInfo, GiveOptions, LabKey, LogEntry,
  LoginResult, Medication, Patient, PatientInput, Permission, Result, Snapshot, User, VitalKey,
} from '../types';
import type { VitalApi } from './index';
import { BED_POOL, CATALOG, SEED_PATIENTS, USERS, drugInfoFor, type SeedPatient } from '../engine/data';
import { can, whyNot } from '../engine/permissions';
import { evaluate } from '../engine/rules';
import { checkNewMedication } from '../engine/checker';
import { expectedDose } from '../engine/doubleCheck';
import { handoffText, sbarText } from '../engine/aiText';
import { AiLedger } from '../engine/aiControl';
import { isActive, isHighAlert } from '../engine/util';

const TICK_MS = 2000;       // real time between monitor updates
const SIM_PER_TICK = 0.5;   // demo minutes per tick
const STEP: Record<VitalKey, number> = { sbp: 6, dbp: 4, hr: 4, rr: 1.6, spo2: 1.3 };
const NOISE: Record<VitalKey, number> = { sbp: 3, dbp: 2, hr: 3, rr: 0.8, spo2: 0.7 };
const VITAL_KEYS: VitalKey[] = ['sbp', 'dbp', 'hr', 'rr', 'spo2'];

interface ScenarioDef {
  key: string; pid: string; label: string; log: string;
  lab?: LabKey; vit?: VitalKey[];
  run: (api: MockApi, p: Patient) => void;
}
interface UndoInfo { at: number; lab: Patient['labs'][LabKey] | null; newMed: string | null }

const SCENARIOS: ScenarioDef[] = [
  { key: 'bp', pid: 'p1', vit: ['sbp', 'dbp', 'hr'], label: 'Blood pressure drops', log: 'Monitor: BP trending down', run: (_a, p) => { p.target.sbp = 82; p.target.dbp = 46; p.target.hr = 52; } },
  { key: 'k', pid: 'p1', lab: 'k', label: 'Potassium result: 5.8', log: 'Lab resulted: K+ 5.8 mmol/L', run: (a, p) => a.setLab(p, 'k', 5.8) },
  { key: 'cr', pid: 'p2', lab: 'cr', label: 'Creatinine rises to 2.8', log: 'Lab resulted: creatinine 2.8 mg/dL', run: (a, p) => a.setLab(p, 'cr', 2.8) },
  { key: 'glu', pid: 'p2', lab: 'glu', label: 'Fingerstick glucose: 58', log: 'POC glucose 58 mg/dL', run: (a, p) => a.setLab(p, 'glu', 58) },
  { key: 'amox', pid: 'p2', label: 'Amoxicillin-clav ordered', log: 'New order: amoxicillin-clavulanate', run: (a, p) => a.addMed(p, { name: 'Amoxicillin-clavulanate', dose: '875 mg', route: 'PO', freq: 'BID', due: '10:00', cls: ['penicillin'] }) },
  { key: 'norco', pid: 'p4', label: 'Norco ordered', log: 'New order: hydrocodone/acetaminophen', run: (a, p) => a.addMed(p, { name: 'Hydrocodone/APAP 5/325', dose: '1 tab', route: 'PO', freq: 'q4h PRN pain', due: 'PRN', cls: ['opioid'], apap: 1950 }) },
  { key: 'resp', pid: 'p4', vit: ['rr', 'spo2', 'hr'], label: 'Breathing slows', log: 'Monitor: RR and SpO2 trending down', run: (_a, p) => { p.target.rr = 9; p.target.spo2 = 88; p.target.hr = 64; } },
  { key: 'inr', pid: 'p3', lab: 'inr', label: 'INR result: 4.8', log: 'Lab resulted: INR 4.8', run: (a, p) => a.setLab(p, 'inr', 4.8) },
  { key: 'hgb', pid: 'p10', lab: 'hgb', label: 'Hemoglobin drops to 6.6', log: 'Lab resulted: hemoglobin 6.6 g/dL', run: (a, p) => a.setLab(p, 'hgb', 6.6) },
  { key: 'nsaid', pid: 'p3', label: 'Ibuprofen ordered', log: 'New order: ibuprofen', run: (a, p) => a.addMed(p, { name: 'Ibuprofen', dose: '600 mg', route: 'PO', freq: 'q6h PRN pain', due: 'PRN', cls: ['NSAID'] }) },
];

function initPatient(seed: SeedPatient): Patient {
  const hist = { sbp: [], dbp: [], hr: [], rr: [], spo2: [] } as Record<VitalKey, number[]>;
  for (let i = 0; i < 24; i++) for (const k of VITAL_KEYS) hist[k].push(Math.round(seed.vit[k] + (Math.random() - 0.5) * (k === 'spo2' || k === 'rr' ? 1 : 4)));
  return {
    ...structuredClone(seed),
    target: { ...seed.vit }, base: { ...seed.vit }, hist,
    meds: seed.meds.map(m => ({ ...structuredClone(m), status: 'due', at: null })),
    tasks: (seed.tasks || []).map(t => ({ ...t, done: false, at: null })),
  };
}

const delay = <T,>(v: T): Promise<T> => Promise.resolve(v);

export class MockApi implements VitalApi {
  private ai = new AiLedger();
  private sim = 0;
  private paused = false;
  private patients: Patient[] = [];
  private alerts: Alert[] = [];
  private seen: Record<string, number> = {};
  private acked: Record<string, boolean> = {};
  private overrides: Record<string, string> = {};
  private used: Record<string, UndoInfo> = {};
  private log: LogEntry[] = [];
  private discharged: DischargedPatient[] = [];
  private listeners = new Set<() => void>();
  private snapshot: Snapshot | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private booted = false;
  private nextId = 100;
  private user: User | null = null;

  constructor() { this.boot(); }

  // ---------- lifecycle ----------
  private boot() {
    this.sim = 0; this.seen = {}; this.acked = {}; this.overrides = {}; this.used = {}; this.log = []; this.discharged = [];
    this.patients = SEED_PATIENTS.map(initPatient);
    this.booted = false;
    this.addLog(`Shift started. Monitoring ${this.patients.length} patients.`);
    this.runRules();
    this.booted = true;
    this.emit();
  }
  start() {
    if (this.timer) return;
    this.timer = setInterval(() => { if (!this.paused) this.tick(); }, TICK_MS);
  }
  subscribe(listener: () => void) { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; }
  getSnapshot() { return this.snapshot; }
  getConnection(): Connection { return 'online'; }

  // ---------- session ----------
  async getUsers(): Promise<User[]> { return USERS.map(({ pin: _pin, ...u }) => u); }
  async login(username: string, pin: string): Promise<LoginResult> {
    const u = USERS.find(x => x.username === username);
    if (!u || u.pin !== pin) return { ok: false, error: 'That PIN doesn’t match. Try again.' };
    const { pin: _pin, ...user } = u;
    this.user = user;
    this.addLog(`${user.name} signed in (${user.title})`);
    this.emit();
    return { ok: true, user };
  }
  async logout() { if (this.user) this.addLog(`${this.user.name} signed out`); this.user = null; this.emit(); }
  getUser() { return this.user; }
  /** Returns an error Result if the signed-in user may not do this. */
  private guard(action: Permission): Result | null {
    if (!this.user) return { ok: false, error: 'Your session ended. Sign in again.' };
    return can(this.user, action) ? null : { ok: false, error: whyNot(action) };
  }
  private by() { return this.user ? ` — ${this.user.name}` : ''; }

  private emit() {
    const active = this.alerts.filter(a => a.sev !== 'info' && !this.resolved(a));
    this.snapshot = structuredClone({
      sim: this.sim, paused: this.paused, patients: this.patients,
      alerts: active, heldBack: this.alerts.filter(a => a.sev === 'info'),
      log: this.log.slice(-60).reverse(), discharged: this.discharged,
      scenarios: SCENARIOS.filter(s => this.byId(s.pid)).map(s => {
        const p = this.byId(s.pid)!;
        return { key: s.key, pid: s.pid, label: s.label, patientLabel: `${p.bed} · ${p.name}`, used: !!this.used[s.key] };
      }),
    });
    this.listeners.forEach(l => l());
  }

  private tick() {
    this.sim += SIM_PER_TICK;
    for (const p of this.patients) {
      for (const k of VITAL_KEYS) {
        const d = p.target[k] - p.vit[k];
        p.vit[k] += Math.max(-STEP[k], Math.min(STEP[k], d)) + (Math.abs(d) < 2 ? (Math.random() - 0.5) * NOISE[k] : 0);
        if (Math.abs(p.vit[k] - p.target[k]) > 4 && Math.abs(d) < 2) p.vit[k] = p.target[k];
        if (k === 'spo2') p.vit[k] = Math.min(100, p.vit[k]);
        p.hist[k].push(Math.round(p.vit[k]));
        if (p.hist[k].length > 30) p.hist[k].shift();
      }
    }
    this.runRules();
    this.emit();
  }

  // ---------- engine ----------
  private byId(pid: string) { return this.patients.find(p => p.id === pid); }
  private med(pid: string, mid: string) { return this.byId(pid)?.meds.find(m => m.id === mid); }
  private addLog(text: string, kind: LogEntry['kind'] = '') { this.log.push({ t: this.sim, text, kind }); }
  private label(p: Patient) { return `${p.bed} ${p.name}`; }

  private resolved(a: Alert): boolean {
    if (this.overrides[a.id]) return true;
    if ((a.sev === 'warn' || !a.meds.length) && this.acked[a.id]) return true;
    if (!a.meds.length) return false;
    const p = this.byId(a.pid);
    return !!p && a.meds.every(id => { const m = p.meds.find(x => x.id === id); return !m || !isActive(m); });
  }

  private runRules() {
    const all = this.patients.flatMap(p => evaluate(p, this.sim));
    const live = new Set(all.map(a => a.id));
    for (const a of all) {
      if (this.seen[a.id] == null) {
        this.seen[a.id] = this.sim;
        const p = this.byId(a.pid)!;
        if (this.booted && a.sev !== 'info') this.addLog(`${this.label(p)} · ${a.title}`, a.sev === 'crit' ? 'crit' : 'warn');
      }
    }
    for (const id in this.seen) if (!live.has(id)) { delete this.seen[id]; delete this.overrides[id]; delete this.acked[id]; }
    this.alerts = all.map(a => ({ ...a, firstSeen: this.seen[a.id] }));
  }
  private commit() { this.runRules(); this.emit(); }

  private activeAlertsFor(pid: string, mid: string) {
    return this.alerts.filter(a => a.pid === pid && a.sev !== 'info' && !a.timing && a.meds.includes(mid) && !this.resolved(a));
  }

  setLab(p: Patient, key: LabKey, v: number) {
    const cur = p.labs[key];
    p.labs[key] = { v, t: this.sim, prev: cur ? cur.v : undefined };
  }
  addMed(p: Patient, m: Omit<Medication, 'id' | 'status' | 'at'>) {
    let n = p.meds.length + 1;
    while (p.meds.some(x => x.id === 'n' + n)) n++;
    p.meds.push({ ...m, id: 'n' + n, status: 'due', at: null, isNew: true, orderedAt: this.sim });
  }

  // ---------- administration ----------
  async checkAdministration(pid: string, mid: string): Promise<AdministrationCheck> {
    const p = this.byId(pid), m = this.med(pid, mid);
    if (!p || !m) return { blocking: [], highAlert: false, expected: null };
    const hi = isHighAlert(m);
    return structuredClone({ blocking: this.activeAlertsFor(pid, mid), highAlert: hi, expected: hi ? expectedDose(p, m) : null });
  }

  async giveMedication(pid: string, mid: string, opts: GiveOptions = {}): Promise<Result> {
    const denied = this.guard('administer'); if (denied) return denied;
    const p = this.byId(pid), m = this.med(pid, mid);
    if (!p || !m || !isActive(m)) return { ok: false, error: 'This order is no longer active.' };
    const blocking = this.activeAlertsFor(pid, mid);
    if (blocking.length && !opts.overrideReason) return { ok: false, error: 'Vital alerts must be reviewed and a reason given before giving.' };
    if (isHighAlert(m)) {
      const e = expectedDose(p, m);
      if (!opts.cosigner) return { ok: false, error: 'High-alert medication: a second nurse must co-sign.' };
      const co = USERS.find(u => u.username === opts.cosigner);
      if (!co || !['nurse', 'charge'].includes(co.role)) return { ok: false, error: 'The co-signer must be a nurse.' };
      if (co.username === this.user!.username) return { ok: false, error: 'The double-check must be done by a different nurse.' };
      if (co.pin !== opts.cosignPin) return { ok: false, error: `${co.name}: that PIN doesn’t match.` };
      if (opts.cosignDose == null || Math.abs(opts.cosignDose - e.n) > 1e-6) {
        this.addLog(`${this.label(p)} · Double-check caught a mismatch on ${m.name}: ${co.name} got ${opts.cosignDose} ${e.unit}, calculated dose is ${e.n} ${e.unit}. Not given.${this.by()}`, 'crit');
        this.emit();
        return { ok: false, error: `Doses don't match. ${co.name} entered ${opts.cosignDose} ${e.unit}, but the calculated dose is ${e.n} ${e.unit}. ${e.calc}. Stop and recalculate together before giving.` };
      }
      m.cosign = co.name;
    }
    if (opts.overrideReason) {
      blocking.forEach(a => { this.overrides[a.id] = opts.overrideReason!; });
      this.addLog(`${this.label(p)} · Override on ${m.name}: "${opts.overrideReason}"${this.by()}`, 'warn');
    }
    m.status = 'given'; m.at = this.sim;
    const e = isHighAlert(m) ? expectedDose(p, m) : null;
    this.addLog(`${this.label(p)} · Gave ${m.name} ${e ? `${e.n} ${e.unit}` : m.dose}.${m.cosign ? ` Double-checked by ${m.cosign}.` : ''}${opts.overrideReason ? '' : ' All checks passed.'}${this.by()}`, opts.overrideReason ? 'warn' : 'ok');
    this.commit();
    return { ok: true };
  }

  async holdMedication(pid: string, mid: string, reason: string): Promise<Result> {
    const denied = this.guard('administer'); if (denied) return denied;
    const p = this.byId(pid), m = this.med(pid, mid);
    if (!p || !m) return { ok: false, error: 'Order not found.' };
    m.status = 'held'; m.at = this.sim;
    this.addLog(`${this.label(p)} · Held ${m.name}. Reason: ${reason}${this.by()}`, 'ok');
    this.commit();
    return { ok: true };
  }

  async holdForAlert(alertId: string): Promise<Result> {
    const denied = this.guard('administer'); if (denied) return denied;
    const a = this.alerts.find(x => x.id === alertId); if (!a) return { ok: false };
    const p = this.byId(a.pid)!;
    const names: string[] = [];
    a.meds.forEach(id => { const m = p.meds.find(x => x.id === id); if (m && isActive(m)) { m.status = 'held'; m.at = this.sim; names.push(m.name); } });
    this.addLog(`${this.label(p)} · Held ${names.join(', ')}. Reason: ${a.title}${this.by()}`, 'ok');
    this.commit();
    return { ok: true };
  }

  async discontinueMedication(pid: string, mid: string): Promise<Result> {
    const denied = this.guard('order'); if (denied) return denied;
    const p = this.byId(pid); if (!p) return { ok: false };
    const m = p.meds.find(x => x.id === mid); if (!m) return { ok: false };
    p.meds = p.meds.filter(x => x !== m);
    for (const k in this.used) if (this.used[k].newMed === mid && SCENARIOS.find(s => s.key === k)?.pid === pid) delete this.used[k];
    this.addLog(`${this.label(p)} · Discontinued ${m.name}${this.by()}`);
    this.commit();
    return { ok: true };
  }

  // ---------- new orders ----------
  async getCatalog(): Promise<CatalogDrug[]> { return delay(structuredClone(CATALOG)); }

  async checkMedication(pid: string, drugKey: string): Promise<CheckIssue[]> {
    const p = this.byId(pid), d = CATALOG.find(x => x.key === drugKey);
    return p && d ? checkNewMedication(p, d) : [];
  }

  async orderMedication(pid: string, drugKey: string, overrideReason?: string): Promise<Result> {
    const denied = this.guard('order'); if (denied) return denied;
    const p = this.byId(pid), d = CATALOG.find(x => x.key === drugKey);
    if (!p || !d) return { ok: false, error: 'Unknown patient or drug.' };
    const issues = checkNewMedication(p, d);
    if (issues.some(i => i.sev === 'crit') && !overrideReason) return { ok: false, error: 'Critical issues found. A reason is required to order anyway.' };
    this.addMed(p, { name: d.name, dose: d.dose, route: d.route, freq: d.freq, due: d.due, cls: d.cls.slice(), apap: d.apap, catKey: d.key });
    this.addLog(`${this.label(p)} · New order: ${d.name} ${d.dose}${overrideReason ? `. Ordered despite Vital warning: "${overrideReason}"` : '. Passed Vital check.'}${this.by()}`, overrideReason ? 'warn' : 'ok');
    this.commit();
    return { ok: true };
  }

  // ---------- alerts & tasks ----------
  async suggestAlternatives(pid: string, drugKey: string): Promise<Alternative[]> {
    const p = this.byId(pid), d = CATALOG.find(x => x.key === drugKey);
    if (!p || !d) return [];
    return CATALOG
      .filter(x => x.group === d.group && x.key !== d.key && !p.meds.some(m => isActive(m) && (m.catKey === x.key || m.name === x.name)))
      .map(x => ({ drug: structuredClone(x), issues: checkNewMedication(p, x) }))
      .filter(a => !a.issues.some(i => i.sev === 'crit'))
      .sort((a, b) => a.issues.length - b.issues.length)
      .slice(0, 3);
  }

  async acknowledgeAlert(alertId: string): Promise<Result> {
    const denied = this.guard('acknowledge'); if (denied) return denied;
    const a = this.alerts.find(x => x.id === alertId); if (!a) return { ok: false };
    this.acked[alertId] = true;
    this.addLog(`${this.label(this.byId(a.pid)!)} · Acknowledged: ${a.title}${this.by()}`);
    this.emit();
    return { ok: true };
  }

  async completeTask(pid: string, taskId: string): Promise<Result> {
    const denied = this.guard('tasks'); if (denied) return denied;
    const p = this.byId(pid), t = p?.tasks.find(x => x.id === taskId);
    if (!p || !t) return { ok: false };
    t.done = true; t.at = this.sim;
    const late = this.sim > t.due + t.grace;
    this.addLog(`${this.label(p)} · Done: ${t.name}${late ? ` (${Math.floor(this.sim - t.due)} min late)` : ''}${this.by()}`, late ? 'warn' : 'ok');
    this.commit();
    return { ok: true };
  }

  // ---------- patients ----------
  private validate(input: PatientInput, exceptPid?: string): string | null {
    if (!input.name.trim()) return 'Enter the patient’s name.';
    if (!(input.age >= 0 && input.age <= 120)) return 'Enter an age between 0 and 120.';
    if (!(input.wt > 0 && input.wt < 400)) return 'Enter a weight in kg. Vital uses it for kidney function and dosing.';
    if (!/^\d{3}[A-D]$/.test(input.bed)) return 'Bed must be a room number and letter, like 412A.';
    const clash = this.patients.find(p => p.bed === input.bed && p.id !== exceptPid);
    if (clash) return `Bed ${input.bed} is taken by ${clash.name}. Choose another bed or tap Random.`;
    if (input.allergies.some(a => !a.agent.trim())) return 'Enter the name of each allergen, or remove that row.';
    return null;
  }

  async admitPatient(input: PatientInput): Promise<Result> {
    const denied = this.guard('admit'); if (denied) return denied;
    const err = this.validate(input); if (err) return { ok: false, error: err };
    const id = 'p' + this.nextId++;
    const p = initPatient({
      id, bed: input.bed, name: input.name.trim(), age: input.age, sex: input.sex, wt: input.wt, dx: input.dx.trim() || 'Admitted',
      conditions: input.conditions, allergies: input.allergies,
      vit: { sbp: 124, dbp: 76, hr: 80, rr: 16, spo2: 97 },
      labs: { k: { v: 4.2, t: this.sim }, cr: { v: 0.9, t: this.sim }, glu: { v: 110, t: this.sim } }, meds: [], tasks: [],
    });
    p.otherConds = input.otherConds;
    this.patients.push(p);
    this.addLog(`${this.label(p)} · Admitted${input.allergies.length ? ` · allergies: ${input.allergies.map(a => a.agent).join(', ')}` : ' · no known drug allergies'}${this.by()}`, 'ok');
    this.commit();
    return { ok: true, id };
  }

  async updatePatient(pid: string, input: PatientInput): Promise<Result> {
    const denied = this.guard('editPatient'); if (denied) return denied;
    const p = this.byId(pid); if (!p) return { ok: false, error: 'Patient not found.' };
    const err = this.validate(input, pid); if (err) return { ok: false, error: err };
    const changes: string[] = [];
    if (p.name !== input.name.trim()) changes.push('name');
    if (p.age !== input.age) changes.push('age');
    if (p.sex !== input.sex) changes.push('gender');
    if (p.wt !== input.wt) changes.push('weight');
    if (p.bed !== input.bed) changes.push(`bed ${p.bed} → ${input.bed}`);
    if (JSON.stringify(p.allergies) !== JSON.stringify(input.allergies)) changes.push('allergies');
    if (p.dx !== input.dx.trim()) changes.push('diagnosis');
    if (p.conditions.join() !== input.conditions.join() || (p.otherConds || []).join() !== input.otherConds.join()) changes.push('conditions');
    Object.assign(p, { name: input.name.trim(), age: input.age, sex: input.sex, wt: input.wt, bed: input.bed, dx: input.dx.trim() || p.dx, conditions: input.conditions, otherConds: input.otherConds, allergies: input.allergies });
    this.addLog(`${this.label(p)} · Patient info updated${changes.length ? ': ' + changes.join(', ') : ''}. Vital re-checked all medications.${this.by()}`);
    this.commit();
    return { ok: true };
  }

  async dischargePatient(pid: string): Promise<Result> {
    const denied = this.guard('discharge'); if (denied) return denied;
    const p = this.byId(pid); if (!p) return { ok: false };
    this.patients = this.patients.filter(x => x !== p);
    this.discharged.unshift({ name: p.name, bed: p.bed, at: this.sim });
    this.addLog(`${this.label(p)} · Discharged. Bed ${p.bed} is now free.${this.by()}`, 'ok');
    this.commit();
    return { ok: true };
  }

  async suggestBed(exceptPid?: string): Promise<string> {
    const taken = new Set(this.patients.filter(p => p.id !== exceptPid).map(p => p.bed));
    const free = BED_POOL.filter(b => !taken.has(b));
    return free.length ? free[Math.floor(Math.random() * free.length)] : '';
  }

  // ---------- Vital AI (template text in demo mode) ----------
  private visibleAlerts(pid: string) { return this.alerts.filter(a => a.pid === pid && a.sev !== 'info' && !this.resolved(a)); }
  async getSbar(pid: string): Promise<AiText> {
    const p = this.byId(pid); if (!p) return { text: '', source: 'template' };
    const text = sbarText(p, this.visibleAlerts(pid));
    return { text, source: 'template', details: this.ai.request('sbar', text, p) };
  }
  async getHandoff(pid: string): Promise<AiText> {
    const p = this.byId(pid); if (!p) return { text: '', source: 'template' };
    const text = handoffText(p, this.visibleAlerts(pid));
    return { text, source: 'template', details: this.ai.request('handoff', text, p) };
  }
  async getAiUsage(): Promise<AiUsage> { return this.ai.summary(); }
  async setAiSettings(s: { mode?: 'on' | 'off'; budgetUsd?: number }): Promise<Result & { usage?: AiUsage }> {
    if (!this.user) return { ok: false, error: 'Your session ended. Sign in again.' };
    if (s.budgetUsd !== undefined && this.user.role !== 'charge') return { ok: false, error: 'Only the charge nurse can change the AI budget.' };
    const before = this.ai.summary();
    const after = this.ai.set(s);
    if (after.mode !== before.mode) this.addLog((after.mode === 'on' ? 'Vital AI turned ON (de-identified text only)' : 'Vital AI turned OFF: templates only, nothing sent to AI') + this.by(), 'warn');
    if (after.budgetUsd !== before.budgetUsd) this.addLog(`Vital AI monthly budget set to $${after.budgetUsd.toFixed(2)}${this.by()}`);
    this.emit();
    return { ok: true, usage: after };
  }
  async sendSbar(pid: string, text: string): Promise<Result> {
    if (!this.user) return { ok: false, error: 'Your session ended. Sign in again.' };
    const p = this.byId(pid); if (!p) return { ok: false, error: 'Patient not found.' };
    const first = text.trim().split('\n')[0].slice(0, 120);
    this.addLog(`${this.label(p)} · SBAR sent to provider: "${first}"${this.by()}`, 'ok');
    this.emit();
    return { ok: true };
  }

  async getDrugInfo(name: string): Promise<DrugInfo | null> { return drugInfoFor(name); }

  // ---------- demo controls ----------
  async triggerScenario(key: string) {
    const s = SCENARIOS.find(x => x.key === key); if (!s) return;
    const p = this.byId(s.pid); if (!p) return;
    const u = this.used[key];
    if (u) {
      if (s.lab && u.lab) p.labs[s.lab] = u.lab as never;
      if (s.vit) s.vit.forEach(k => { p.target[k] = p.base[k]; });
      if (u.newMed) p.meds = p.meds.filter(m => m.id !== u.newMed);
      p.meds.forEach(m => { if (!isActive(m) && (m.at ?? -1) >= u.at) { m.status = 'due'; m.at = null; } });
      delete this.used[key];
      this.addLog(`${this.label(p)} · Undid: ${s.label}`);
    } else {
      const info: UndoInfo = { at: this.sim, lab: s.lab ? structuredClone(p.labs[s.lab]) ?? null : null, newMed: null };
      const before = p.meds.length;
      s.run(this, p);
      info.newMed = p.meds.length > before ? p.meds[p.meds.length - 1].id : null;
      this.used[key] = info;
      this.addLog(`${this.label(p)} · ${s.log}`);
    }
    this.commit();
  }
  async resetDemo() { const u = this.user; this.boot(); this.ai = new AiLedger(); this.user = u; this.emit(); }
  async skipMinutes(minutes: number) { this.sim += minutes - SIM_PER_TICK; this.addLog(`Clock moved forward ${minutes} min (demo)`); this.tick(); }
  async setPaused(paused: boolean) { this.paused = paused; this.emit(); }
}


import type { Medication, Patient, Severity, Vitals } from '../types';

/** Demo clock starts at 08:40. `sim` is minutes since then. */
export const BASE_MINUTES = 8 * 60 + 40;

export function fmt(sim: number): string {
  const t = Math.floor(BASE_MINUTES + sim);
  return String(Math.floor(t / 60) % 24).padStart(2, '0') + ':' + String(t % 60).padStart(2, '0');
}

export const roundVitals = (v: Vitals): Vitals => ({
  sbp: Math.round(v.sbp), dbp: Math.round(v.dbp), hr: Math.round(v.hr), rr: Math.round(v.rr), spo2: Math.min(100, Math.round(v.spo2)),
});

/** Cockcroft-Gault creatinine clearance, mL/min. */
export function crcl(p: Patient): number {
  let c = ((140 - p.age) * p.wt) / (72 * p.labs.cr.v);
  if (p.sex === 'F') c *= 0.85;
  return Math.round(c);
}

export const isActive = (m: Medication) => m.status !== 'given' && m.status !== 'held';

export const isHighAlert = (m: Medication) =>
  m.cls.some(c => ['insulin', 'anticoag', 'opioid'].includes(c)) || (m.cls.includes('Ksupp') && m.route === 'IV');

export const highAlertReason = (m: Medication) =>
  m.cls.includes('insulin') ? 'Insulin' : m.cls.includes('anticoag') ? 'Anticoagulant' : m.cls.includes('opioid') ? 'Opioid' : 'IV potassium';

export const sevRank = (s: Severity) => ({ crit: 0, warn: 1, info: 2 }[s]);

export function listNames(meds: { name: string }[]): string {
  const n = meds.map(m => m.name);
  return n.length < 2 ? n[0] : n.slice(0, -1).join(', ') + ' and ' + n[n.length - 1];
}

export function hash(s: string): string {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return (h >>> 0).toString(36);
}

export function firstName(p: Patient) { return p.name.split(' ')[0]; }

/** Countdown state for a time-critical item. */
export function timeState(sim: number, due: number, grace: number, done: boolean): { cls: 'ok' | 'warn' | 'crit' | 'done'; text: string } {
  const left = due - sim;
  if (done) return { cls: 'done', text: 'Done' };
  if (left <= -grace) return { cls: 'crit', text: `${Math.max(1, Math.floor(-left))} min late` };
  if (left <= 0) return { cls: 'warn', text: `${Math.floor(-left)} min late · critical in ${Math.ceil(grace + left)} min` };
  if (left <= 15) return { cls: 'warn', text: `Due in ${Math.ceil(left)} min` };
  return { cls: 'ok', text: `${Math.ceil(left)} min left` };
}

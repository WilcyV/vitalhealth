import type { ExpectedDose, Medication, Patient } from '../types';
import { fmt } from './util';

/** Insulin lispro sliding scale used by the demo order set. */
export function slidingScale(glucose: number): number {
  return glucose <= 150 ? 0 : glucose <= 200 ? 2 : glucose <= 250 ? 4 : glucose <= 300 ? 6 : glucose <= 350 ? 8 : 10;
}

export const SLIDING_SCALE_TEXT = '≤150: 0 · 151–200: 2 · 201–250: 4 · 251–300: 6 · 301–350: 8 · >350: 10 units + call provider';

/** The dose the second nurse must independently arrive at. */
export function expectedDose(p: Patient, m: Medication): ExpectedDose {
  if (m.cls.includes('insulin')) {
    const g = p.labs.glu.v, n = slidingScale(g);
    const band = g <= 150 ? '≤ 150 = 0' : g <= 200 ? '151–200 = 2' : g <= 250 ? '201–250 = 4' : g <= 300 ? '251–300 = 6' : g <= 350 ? '301–350 = 8' : '> 350 = 10 (call provider)';
    return { n, unit: 'units', calc: `Glucose ${g} mg/dL at ${p.labs.glu.t < 0 ? 'last check' : fmt(p.labs.glu.t)} → sliding scale ${band} units` };
  }
  const mm = /^([\d.]+)\s*(.*)$/.exec(m.dose);
  return { n: mm ? parseFloat(mm[1]) : NaN, unit: mm ? mm[2] : '', calc: `Ordered dose: ${m.dose} ${m.route}` };
}

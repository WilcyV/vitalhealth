// Template versions of the Vital AI texts (same as backend/vital_ai/sbar.py and handoff.py).
// In demo mode these are what the "Notify provider" and "Handoff" buttons show.
import type { Alert, Patient } from '../types';
import { crcl, fmt, roundVitals, sevRank } from './util';

const n = (x: number) => String(Number(x.toFixed(4)));

export function sbarText(p: Patient, alerts: Alert[]): string {
  const v = roundVitals(p.vit);
  const main = alerts.slice().sort((a, b) => sevRank(a.sev) - sevRank(b.sev))[0];
  const meds = p.meds.filter(m => m.status === 'due').map(m => `${m.name} ${m.dose} ${m.route}`).join(', ') || 'none due';
  const allergies = p.allergies.map(a => a.agent).join(', ') || 'no known drug allergies';
  return [
    `S: ${p.name}, bed ${p.bed}. ` + (main ? `${main.title}.` : 'No active Vital alerts.'),
    `B: ${p.age}${p.sex}, ${p.dx}. Allergies: ${allergies}. Due meds: ${meds}.`,
    `A: BP ${v.sbp}/${v.dbp}, HR ${v.hr}, RR ${v.rr}, SpO2 ${v.spo2}%. K+ ${n(p.labs.k.v)}, CrCl ${crcl(p)} mL/min.` + (main ? ` ${main.why}` : ''),
    main ? `R: ${main.action} Please advise.` : 'R: For your awareness.',
  ].join('\n');
}

export function handoffText(p: Patient, alerts: Alert[]): string {
  const held = p.meds.filter(m => m.status === 'held');
  const given = p.meds.filter(m => m.status === 'given');
  const open = p.tasks.filter(t => !t.done);
  const lines = [`${p.bed} ${p.name} — ${p.dx}.`];
  const act = alerts.filter(a => a.sev !== 'info');
  if (act.length) lines.push('Open alerts: ' + act.map(a => a.title).join('; ') + '.');
  if (held.length) lines.push('Held: ' + held.map(m => m.name).join(', ') + '.');
  if (given.length) lines.push('Given this shift: ' + given.map(m => `${m.name} at ${fmt(m.at ?? 0)}`).join(', ') + '.');
  if (open.length) lines.push('Still due: ' + open.map(t => `${t.name} by ${fmt(t.due + t.grace)}`).join(', ') + '.');
  return lines.join(' ');
}

import type { LabValue, Patient } from '../types';
import { crcl, fmt } from '../engine/util';

function Row({ sim, name, lab, unit, lo, hi, range, extra }: { sim: number; name: string; lab?: LabValue; unit: string; lo: number; hi: number; range: string; extra?: string }) {
  if (!lab) return null;
  const out = lab.v < lo || lab.v > hi, isNew = sim - lab.t < 8;
  return (
    <tr className={out ? 'flag-crit' : ''}>
      <td>{name}{isNew && <span className="new">NEW</span>}{extra && <span className="sub">{extra}</span>}</td>
      <td className={`num ${out ? 'hi' : ''}`}>{lab.v} <span style={{ color: 'var(--muted)' }}>{unit}</span></td>
      <td className="num" style={{ color: 'var(--muted)' }}>{lab.prev ?? '—'}</td>
      <td className="num" style={{ color: 'var(--muted)' }}>{range}</td>
      <td className="num" style={{ color: 'var(--muted)' }}>{lab.t < 0 ? 'Earlier' : fmt(lab.t)}</td>
    </tr>
  );
}

export function LabsTable({ sim, p }: { sim: number; p: Patient }) {
  const f = p.sex === 'F';
  return (
    <section className="panel section">
      <h3>Labs</h3>
      <div className="tbl-wrap">
        <table>
          <thead><tr><th>Test</th><th>Result</th><th>Previous</th><th>Range</th><th>Time</th></tr></thead>
          <tbody>
            <Row sim={sim} name="Potassium" lab={p.labs.k} unit="mmol/L" lo={3.5} hi={5.0} range="3.5–5.0" />
            <Row sim={sim} name="Creatinine" lab={p.labs.cr} unit="mg/dL" lo={0.6} hi={1.3} range="0.6–1.2" extra={`Est. CrCl ${crcl(p)} mL/min`} />
            <Row sim={sim} name="Glucose" lab={p.labs.glu} unit="mg/dL" lo={70} hi={180} range="70–180" />
            <Row sim={sim} name="INR" lab={p.labs.inr} unit="" lo={2} hi={3} range="2.0–3.0 (on warfarin)" />
            <Row sim={sim} name="Hemoglobin" lab={p.labs.hgb} unit="g/dL" lo={f ? 12 : 13.5} hi={f ? 15.5 : 17.5} range={f ? '12.0–15.5' : '13.5–17.5'} />
            <Row sim={sim} name="Lactate" lab={p.labs.lac} unit="mmol/L" lo={0} hi={2} range="< 2.0" />
          </tbody>
        </table>
      </div>
    </section>
  );
}

import { useEffect, useState } from 'react';
import type { Alert, DrugInfo, Medication, Patient } from '../../types';
import { api } from '../../api';
import { crcl, firstName, fmt, isActive, isHighAlert, roundVitals, timeState } from '../../engine/util';
import { Modal } from './Modal';

export function DrugInfoModal({ p, m, alerts, sim, onClose }: { p: Patient; m: Medication; alerts: Alert[]; sim: number; onClose: () => void }) {
  const [info, setInfo] = useState<DrugInfo | null | undefined>(undefined);
  useEffect(() => { api.getDrugInfo(m.name).then(setInfo); }, [m.name]);
  const v = roundVitals(p.vit);
  const now: string[] = [];
  if (m.param) now.push(`Order parameter: ${m.param}. Current BP ${v.sbp}/${v.dbp}, HR ${v.hr}.`);
  if (isHighAlert(m)) now.push('High-alert medication: needs an independent double-check before giving.');
  if (m.tc) now.push(`Time-critical: due by ${fmt(m.tc.due + m.tc.grace)} (${timeState(sim, m.tc.due, m.tc.grace, !isActive(m)).text}).`);
  if (m.renal || m.cls.includes('LMWH') || m.cls.includes('metformin')) now.push(`Cleared by the kidneys. Est. CrCl ${crcl(p)} mL/min.`);
  const mine = alerts.filter(a => a.pid === p.id && a.meds.includes(m.id));
  mine.forEach(a => now.push(`${a.sev === 'crit' ? 'Critical' : 'Warning'}: ${a.title}`));
  if (!mine.length) now.push('No active Vital alerts for this medication.');
  return (
    <Modal eyebrow="Vital · Drug info" title={`${m.name} ${m.dose} ${m.route} · ${m.freq}`} onClose={onClose} className="info"
      footer={<button className="btn primary" onClick={onClose} data-autofocus>Close</button>}>
      {info === undefined ? <p>Loading…</p> : info ? (
        <dl><dt>Class</dt><dd>{info.cls}</dd><dt>Used for</dt><dd>{info.use}</dd><dt>Watch for</dt><dd>{info.watch}</dd><dt>Nursing</dt><dd>{info.nursing}</dd></dl>
      ) : <p>No reference entry for this drug yet.</p>}
      <div>
        <h3 className="mini">For {firstName(p)} right now</h3>
        <ul>{now.map((x, i) => <li key={i}>{x}</li>)}</ul>
      </div>
      <p className="decide">Reference summary. In production this comes from the hospital's drug database.</p>
    </Modal>
  );
}

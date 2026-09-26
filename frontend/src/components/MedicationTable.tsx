import type { Medication, Patient, Snapshot } from '../types';
import { fmt, isActive, isHighAlert, timeState } from '../engine/util';
import { api } from '../api';
import { Chip } from './ui';
import { AsyncButton } from './AsyncButton';
import { can, whyNot } from '../engine/permissions';
import { useUser } from '../hooks/useSession';

interface Props { snap: Snapshot; p: Patient; onGive: (pid: string, mid: string) => void; onInfo: (pid: string, mid: string) => void }

export function MedicationTable({ snap, p, onGive, onInfo }: Props) {
  const user = useUser();
  const canGive = can(user, 'administer');
  const alertsFor = (m: Medication) => snap.alerts.filter(a => a.pid === p.id && a.meds.includes(m.id) && !a.timing);
  return (
    <section className="panel section">
      <h3>Medications due <span>re-checked on every change</span></h3>
      <div className="tbl-wrap">
        <table>
          <thead><tr><th>Due</th><th>Order</th><th>Status</th><th><span className="sr">Actions</span></th></tr></thead>
          <tbody>
            {p.meds.length === 0 && <tr><td colSpan={4} className="empty">No medications ordered yet. Use "Check a new medication" below to add one safely.</td></tr>}
            {p.meds.map(m => {
              const al = alertsFor(m), s = al.some(a => a.sev === 'crit') ? 'crit' : al.length ? 'warn' : '';
              const active = isActive(m);
              const tc = m.tc ? timeState(snap.sim, m.tc.due, m.tc.grace, !active) : null;
              let chip: React.ReactNode;
              if (m.status === 'given') chip = <Chip kind="ok" title={m.cosign ? `Double-checked by ${m.cosign}` : undefined}>Given {fmt(m.at!)}{m.cosign ? ' · 2 RN' : ''}</Chip>;
              else if (m.status === 'held') chip = <Chip kind="neutral">Held {fmt(m.at!)}</Chip>;
              else if (s === 'crit') chip = <Chip kind="crit" pulse>Hold</Chip>;
              else if (tc?.cls === 'crit') chip = <Chip kind="crit" pulse>Late</Chip>;
              else if (m.tc && snap.sim >= m.tc.due - 15) chip = <Chip kind="warn">Due now</Chip>;
              else if (s === 'warn') chip = <Chip kind="warn">Review</Chip>;
              else chip = <Chip kind="ok">Clear</Chip>;
              return (
                <tr key={m.id} className={s && active ? `flag-${s}` : ''}>
                  <td className="num">{m.due}</td>
                  <td>
                    <button className="mname" onClick={() => onInfo(p.id, m.id)} title="Drug info">{m.name}<span className="i" aria-hidden="true">ⓘ</span></button>
                    {m.isNew && <span className="new">NEW ORDER</span>}
                    {isHighAlert(m) && <span className="ha" title="High-alert medication: needs an independent double-check">HIGH-ALERT</span>}
                    <span className="sub">{m.dose} · {m.route} · {m.freq}{m.param ? ' · ' + m.param : ''}</span>
                    {m.tc && tc && <span className={`tcl ${tc.cls}`}>⏱ Time-critical · due by {fmt(m.tc.due + m.tc.grace)}{active ? ' · ' + tc.text : ''}</span>}
                  </td>
                  <td>{chip}</td>
                  <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                    {m.isNew && active && <AsyncButton perm="order" action={() => api.discontinueMedication(p.id, m.id)} title="Discontinue this order" aria-label={`Discontinue ${m.name}`}>D/C</AsyncButton>}{' '}
                    {active && <button className={`btn ${s === 'crit' ? '' : 'primary'}`} onClick={() => onGive(p.id, m.id)} disabled={!canGive} title={canGive ? undefined : whyNot('administer')} aria-label={`${m.due === 'PRN' ? 'Give PRN' : 'Scan and give'} ${m.name}`}>{m.due === 'PRN' ? 'Give PRN' : 'Scan & give'}</button>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

import type { Snapshot } from '../types';
import { fmt } from '../engine/util';
import { PatientStatus } from './ui';
import { can, whyNot } from '../engine/permissions';
import { useUser } from '../hooks/useSession';

interface Props { snap: Snapshot; selected: string | null; onSelect: (pid: string) => void; onAdmit: () => void }

export function PatientList({ snap, selected, onSelect, onAdmit }: Props) {
  const user = useUser();
  const sorted = snap.patients.slice().sort((a, b) => a.bed.localeCompare(b.bed));
  return (
    <aside className="panel">
      <div className="panel-h">
        <h2>Patients</h2>
        <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span className="chip neutral">{snap.patients.length} assigned</span>
          <button className="btn sm primary" onClick={onAdmit} disabled={!can(user, 'admit')} title={can(user, 'admit') ? 'Admit a new patient' : whyNot('admit')}>+ Admit</button>
        </span>
      </div>
      <div className="plist">
        {sorted.length === 0 && <div className="empty">No patients assigned.<br />Tap + Admit to add one.</div>}
        {sorted.map(p => (
          <button key={p.id} className={`pt ${p.id === selected ? 'sel' : ''}`} onClick={() => onSelect(p.id)} aria-current={p.id === selected}>
            <span className="bed">{p.bed}</span>
            <span className="nm">{p.name}<PatientStatus alerts={snap.alerts} pid={p.id} /></span>
            <span className="dx">{p.age}{p.sex} · {p.dx}</span>
          </button>
        ))}
      </div>
      {snap.discharged.length > 0 && (
        <details className="held">
          <summary>Discharged today ({snap.discharged.length})</summary>
          <div className="log">{snap.discharged.map((d, i) => <div key={i}><span className="mono">{fmt(d.at)}</span><span>{d.bed} · {d.name}</span></div>)}</div>
        </details>
      )}
    </aside>
  );
}

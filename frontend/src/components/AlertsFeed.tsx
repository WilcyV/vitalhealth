import type { Snapshot } from '../types';
import { sevRank } from '../engine/util';
import { AlertCard } from './AlertCard';

export function AlertsFeed({ snap, onOpenPatient, fresh }: { snap: Snapshot; onOpenPatient: (pid: string) => void; fresh: Set<string> }) {
  const byId = (pid: string) => snap.patients.find(p => p.id === pid);
  const active = snap.alerts.filter(a => byId(a.pid)).sort((x, y) => sevRank(x.sev) - sevRank(y.sev) || y.firstSeen - x.firstSeen);
  return (
    <section className="panel">
      <div className="panel-h"><h2>Vital alerts · all patients</h2><span className="chip neutral">sorted by severity</span></div>
      {active.length ? (
        <div className="feed">{active.map(a => <AlertCard key={a.id} alert={a} patient={byId(a.pid)!} onOpenPatient={onOpenPatient} fresh={fresh.has(a.id)} />)}</div>
      ) : (
        <div className="empty"><b>No active alerts</b>All due medications pass every check.</div>
      )}
      <details className="held">
        <summary>{snap.heldBack.length} low-priority checks held back</summary>
        <div className="feed">{snap.heldBack.filter(a => byId(a.pid)).map(a => <AlertCard key={a.id} alert={a} patient={byId(a.pid)!} onOpenPatient={onOpenPatient} />)}</div>
      </details>
    </section>
  );
}

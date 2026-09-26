import type { Patient, Snapshot } from '../types';
import { BED_POOL } from '../engine/data';
import { fmt, isActive, isHighAlert, timeState } from '../engine/util';

/** Charge-nurse view: every bed on the unit, colored by risk, with what needs attention next. */
export function UnitView({ snap, onOpen }: { snap: Snapshot; onOpen: (pid: string) => void }) {
  const byBed = new Map(snap.patients.map(p => [p.bed, p]));
  const extraBeds = snap.patients.map(p => p.bed).filter(b => !BED_POOL.includes(b));
  const beds = [...BED_POOL, ...extraBeds];
  const info = (p: Patient) => {
    const al = snap.alerts.filter(a => a.pid === p.id);
    const crit = al.filter(a => a.sev === 'crit').length, warn = al.filter(a => a.sev === 'warn').length;
    const timed = [...p.meds.filter(m => m.tc && isActive(m)).map(m => ({ name: m.name, due: m.tc!.due, grace: m.tc!.grace })),
      ...p.tasks.filter(t => !t.done).map(t => ({ name: t.name, due: t.due, grace: t.grace }))].sort((a, b) => a.due - b.due);
    const late = timed.filter(t => timeState(snap.sim, t.due, t.grace, false).cls === 'crit').length;
    const hi = p.meds.filter(m => isActive(m) && isHighAlert(m)).length;
    const score = crit * 3 + warn + late * 2;
    const level = crit || late ? 'crit' : warn ? 'warn' : 'ok';
    return { crit, warn, late, hi, next: timed[0], score, level };
  };
  const rows = snap.patients.map(p => ({ p, ...info(p) }));
  const sum = (k: 'crit' | 'warn' | 'late') => rows.reduce((s, r) => s + r[k], 0);
  const attention = rows.filter(r => r.score > 0).sort((a, b) => b.score - a.score);
  return (
    <main className="detail" id="main">
      <section className="panel section">
        <h3>Unit overview <span>4 West · {fmt(snap.sim)}</span></h3>
        <div className="unitstats">
          <div><b>{snap.patients.length}</b><span>patients</span></div>
          <div className="crit"><b>{sum('crit')}</b><span>critical alerts</span></div>
          <div className="warn"><b>{sum('warn')}</b><span>warnings</span></div>
          <div className="crit"><b>{sum('late')}</b><span>late time-critical items</span></div>
          <div><b>{BED_POOL.length - snap.patients.filter(p => BED_POOL.includes(p.bed)).length}</b><span>open beds</span></div>
        </div>
      </section>
      <section className="panel section">
        <h3>Beds by risk <span>tap a bed to open the patient</span></h3>
        <div className="legend"><span className="lg crit">Critical or late</span><span className="lg warn">Warning</span><span className="lg ok">Stable</span><span className="lg empty">Open bed</span></div>
        <div className="beds">
          {beds.map(b => {
            const p = byBed.get(b);
            if (!p) return <div key={b} className="bedtile empty" aria-label={`Bed ${b}, open`}><span className="bn">{b}</span><span className="muted small">Open</span></div>;
            const r = info(p);
            return (
              <button key={b} className={`bedtile ${r.level}`} onClick={() => onOpen(p.id)} aria-label={`Bed ${b}, ${p.name}, ${r.crit} critical, ${r.warn} warnings`}>
                <span className="bn">{b}</span>
                <b>{p.name}</b>
                <span className="small">{p.age}{p.sex} · {p.dx}</span>
                <span className="bt">
                  {r.crit > 0 && <span className="chip crit">{r.crit} crit</span>}
                  {r.warn > 0 && <span className="chip warn">{r.warn} warn</span>}
                  {r.late > 0 && <span className="chip crit">{r.late} late</span>}
                  {r.hi > 0 && <span className="chip neutral">{r.hi} high-alert</span>}
                </span>
                {r.next && <span className="small nx">Next: {r.next.name} · {timeState(snap.sim, r.next.due, r.next.grace, false).text}</span>}
              </button>
            );
          })}
        </div>
      </section>
      <section className="panel section">
        <h3>Needs attention first <span>ranked by risk</span></h3>
        {attention.length === 0 ? <p className="muted">Every patient is stable right now.</p> : (
          <ol className="rank">
            {attention.map(r => (
              <li key={r.p.id}>
                <button className="linkbtn big" onClick={() => onOpen(r.p.id)}>{r.p.bed} · {r.p.name}</button>
                <span className="muted small">{[r.crit && `${r.crit} critical`, r.warn && `${r.warn} warning${r.warn > 1 ? 's' : ''}`, r.late && `${r.late} late`].filter(Boolean).join(' · ')}</span>
              </li>
            ))}
          </ol>
        )}
      </section>
    </main>
  );
}

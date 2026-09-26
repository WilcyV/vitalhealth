import type { Patient } from '../types';
import { fmt, isActive, timeState } from '../engine/util';
import { api } from '../api';
import { Chip } from './ui';
import { AsyncButton } from './AsyncButton';
import { can, whyNot } from '../engine/permissions';
import { useUser } from '../hooks/useSession';

export function TimeCriticalPanel({ sim, p, onGive }: { sim: number; p: Patient; onGive: (pid: string, mid: string) => void }) {
  const user = useUser();
  const items = [
    ...p.meds.filter(m => m.tc).map(m => ({ key: 'm' + m.id, kind: 'med' as const, id: m.id, name: `${m.name} ${m.dose} ${m.route}`, due: m.tc!.due, grace: m.tc!.grace, why: m.tc!.why, done: !isActive(m), at: m.at, held: m.status === 'held' })),
    ...p.tasks.map(t => ({ key: 't' + t.id, kind: 'task' as const, id: t.id, name: t.name, due: t.due, grace: t.grace, why: t.why, done: t.done, at: t.at, held: false })),
  ].sort((a, b) => Number(a.done) - Number(b.done) || a.due - b.due);
  if (!items.length) return null;
  return (
    <section className="panel section">
      <h3>Time-critical <span>counts down on its own · escalates if late</span></h3>
      <div className="tasks">
        {items.map(x => {
          const st = timeState(sim, x.due, x.grace, x.done), left = x.due - sim;
          const pct = x.done ? 100 : Math.max(0, Math.min(100, 100 - (left / 60) * 100));
          const col = st.cls === 'crit' ? 'var(--crit)' : st.cls === 'warn' ? 'var(--warn)' : st.cls === 'done' ? 'var(--muted)' : 'var(--accent)';
          return (
            <div key={x.key} className={`task ${st.cls}`}>
              <div>
                <b>{x.name}</b>{' '}
                <span className="mono" style={{ color: 'var(--muted)', fontSize: 12 }}>· {x.kind === 'med' ? 'medication' : 'care task'} · due {fmt(x.due)}{x.grace ? ` (+${x.grace} min window)` : ''}</span>
                <p>{x.why}</p>
              </div>
              <div className="tr">
                {x.done
                  ? <Chip kind={x.held ? 'neutral' : 'ok'}>{x.held ? 'Held' : 'Done'} {fmt(x.at!)}</Chip>
                  : <Chip kind={st.cls === 'ok' ? 'info' : (st.cls as 'warn' | 'crit')} pulse={st.cls === 'crit'}>{st.text}</Chip>}
                {!x.done && (x.kind === 'task'
                  ? <AsyncButton className="btn primary" perm="tasks" action={() => api.completeTask(p.id, x.id)} aria-label={`Mark done: ${x.name}`}>Mark done</AsyncButton>
                  : <button className="btn primary" onClick={() => onGive(p.id, x.id)} disabled={!can(user, 'administer')} title={can(user, 'administer') ? undefined : whyNot('administer')}>Scan &amp; give</button>)}
              </div>
              <div className="bar"><i style={{ width: `${pct}%`, background: col }} /></div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

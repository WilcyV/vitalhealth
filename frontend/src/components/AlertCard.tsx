import type { Alert, Patient } from '../types';
import { fmt } from '../engine/util';
import { Chip, sevLabel } from './ui';
import { api } from '../api';
import { AsyncButton } from './AsyncButton';

interface Props { alert: Alert; patient: Patient; full?: boolean; onOpenPatient?: (pid: string) => void; fresh?: boolean }

export function AlertCard({ alert: a, patient: p, full, onOpenPatient, fresh }: Props) {
  return (
    <article className={`acard ${a.sev} ${fresh && a.sev === 'crit' ? 'new-crit' : ''}`}>
      <div className="ah">
        <span className="at">
          {!full && <><span className="mono" style={{ color: 'var(--muted)', fontWeight: 600 }}>{p.bed}</span> · </>}
          {a.title}
        </span>
        <Chip kind={a.sev}>{sevLabel(a.sev)}</Chip>
      </div>
      {full ? (
        <>
          <p>{a.why}</p>
          {a.data.length > 0 && <ul>{a.data.map((d, i) => <li key={i}>{d}</li>)}</ul>}
          {a.action && <div className="act"><b>Suggested:</b> {a.action}</div>}
        </>
      ) : (
        <p style={{ color: 'var(--muted)' }}>{p.name} · {a.why.split('. ')[0]}.</p>
      )}
      <div className="row">
        <span className="trig">{a.trigger} · {fmt(a.firstSeen)}</span>
        <span style={{ display: 'flex', gap: 6 }}>
          {!full && onOpenPatient && <button className="btn" onClick={() => onOpenPatient(p.id)}>Open patient</button>}
          {full && a.sev === 'crit' && a.meds.length > 0 && !a.timing && (
            <AsyncButton className="btn danger" perm="administer" action={() => api.holdForAlert(a.id)}>Hold {a.meds.length > 1 ? 'doses' : 'dose'}</AsyncButton>
          )}
          {a.task ? (
            <AsyncButton className="btn primary" perm="tasks" action={() => api.completeTask(p.id, a.task!)}>Mark done</AsyncButton>
          ) : (a.sev === 'warn' || !a.meds.length) && a.sev !== 'info' ? (
            <AsyncButton className="btn" perm="acknowledge" action={() => api.acknowledgeAlert(a.id)}>Acknowledge</AsyncButton>
          ) : null}
        </span>
      </div>
    </article>
  );
}

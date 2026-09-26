import type { Snapshot } from '../types';
import { fmt } from '../engine/util';
import { api, isDemoMode } from '../api';
import type { User } from '../types';
import { ROLE_LABEL } from '../engine/permissions';
import { AsyncButton } from './AsyncButton';

export type View = 'patients' | 'unit';

export function Header({ snap, user, view, onView }: { snap: Snapshot; user: User; view: View; onView: (v: View) => void }) {
  const c = snap.alerts.filter(a => a.sev === 'crit').length;
  const w = snap.alerts.filter(a => a.sev === 'warn').length;
  return (
    <header className="top">
      <div className="brand">
        <div className="mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="var(--accent-ink)" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3z" /><path d="M8 12.5h2l1.2-2.5 1.8 4.5 1.2-2H16" />
          </svg>
        </div>
        <div><h1>VitalHealth</h1><small>Vital AI · 4 West · Med-Surg · {snap.patients.length} patients · RN view</small></div>
      </div>
      <div className="kpis" aria-live="polite">
        <div className="kpi crit"><b>{c}</b><span>critical</span></div>
        <div className="kpi warn"><b>{w}</b><span>warnings</span></div>
        <div className="kpi info" title="A typical system would show all of these"><b>{snap.heldBack.length}</b><span>low-priority held back</span></div>
      </div>
      <div className="clock">
        <span className={`live ${snap.paused ? 'off' : ''}`} />
        <span>{isDemoMode ? 'Sim time' : 'Time'} <span className="mono">{fmt(snap.sim)}</span></span>
        {isDemoMode && <>
          <AsyncButton action={() => api.skipMinutes(15)} title="Jump the clock forward to see time-critical items escalate">+15 min</AsyncButton>
          <AsyncButton action={() => api.setPaused(!snap.paused)}>{snap.paused ? 'Resume feed' : 'Pause feed'}</AsyncButton>
        </>}
      </div>
      <div className="userbar">
        <div className="tabs" role="tablist" aria-label="View">
          <button role="tab" aria-selected={view === 'patients'} className={view === 'patients' ? 'on' : ''} onClick={() => onView('patients')}>Patients</button>
          <button role="tab" aria-selected={view === 'unit'} className={view === 'unit' ? 'on' : ''} onClick={() => onView('unit')}>Unit view</button>
        </div>
        <span className="who"><b>{user.name}</b><span className="chip neutral">{ROLE_LABEL[user.role]}</span></span>
        <AsyncButton className="btn sm" action={() => api.logout()}>Switch user</AsyncButton>
      </div>
    </header>
  );
}

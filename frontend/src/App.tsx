import { useCallback, useEffect, useRef, useState } from 'react';
import type { AdministrationCheck } from './types';
import { api, isDemoMode } from './api';
import { useVital } from './hooks/useVital';
import { Header, type View } from './components/Header';
import { Login } from './components/Login';
import { UnitView } from './components/UnitView';
import { NoticeProvider, NETWORK_ERROR, useNotify } from './components/Notices';
import { useConnection, useUser } from './hooks/useSession';
import { fmt } from './engine/util';
import { DemoControls } from './components/DemoControls';
import { PatientList } from './components/PatientList';
import { PatientPage } from './components/PatientPage';
import { AlertsFeed } from './components/AlertsFeed';
import { ActivityLog } from './components/ActivityLog';
import { Toasts, type ToastItem } from './components/Toasts';
import { AdministerModal } from './components/modals/AdministerModal';
import { DoubleCheckModal } from './components/modals/DoubleCheckModal';
import { DrugInfoModal } from './components/modals/DrugInfoModal';
import { PatientFormModal } from './components/modals/PatientFormModal';
import { DischargeModal } from './components/modals/DischargeModal';
import { AiTextModal } from './components/modals/AiTextModal';
import { AiControlModal } from './components/modals/AiControlModal';

type ModalState =
  | null
  | { kind: 'administer'; pid: string; mid: string; check: AdministrationCheck }
  | { kind: 'double'; pid: string; mid: string; check: AdministrationCheck; overrideReason?: string }
  | { kind: 'info'; pid: string; mid: string }
  | { kind: 'patient'; pid?: string }
  | { kind: 'discharge'; pid: string }
  | { kind: 'sbar' | 'handoff'; pid: string }
  | { kind: 'aictl' };

export default function App() {
  return <NoticeProvider><Shell /></NoticeProvider>;
}

function Shell() {
  const snap = useVital();
  const user = useUser();
  const connection = useConnection();
  const notify = useNotify();
  const [view, setView] = useState<View>('patients');
  const [selected, setSelected] = useState<string | null>('p1');
  const [modal, setModal] = useState<ModalState>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  const seenCrit = useRef<Set<string> | null>(null);

  useEffect(() => { api.start(); }, []);

  // Pop a notification the first time a critical alert appears.
  useEffect(() => {
    if (!snap) return;
    const crit = snap.alerts.filter(a => a.sev === 'crit');
    if (seenCrit.current) {
      const added = crit.filter(a => !seenCrit.current!.has(a.id));
      if (added.length) {
        const pt = (pid: string) => snap.patients.find(p => p.id === pid);
        let items: ToastItem[];
        if (added.length > 2) {
          // Several at once (e.g. after skipping time): one summary instead of a wall of pop-ups.
          const names = [...new Set(added.map(a => pt(a.pid)?.name).filter(Boolean))];
          items = [{ id: 'grp:' + Date.now(), pid: added[0].pid, eyebrow: 'Vital · Critical', title: `${added.length} new critical alerts`, sub: names.slice(0, 3).join(', ') + (names.length > 3 ? ` +${names.length - 3} more` : '') }];
        } else {
          items = added.filter(a => pt(a.pid)).map(a => { const p = pt(a.pid)!; return { id: a.id + ':' + Date.now(), pid: p.id, eyebrow: `Vital · Critical · ${p.bed}`, title: a.title, sub: `${p.name} · ${a.trigger}` }; });
        }
        setToasts(t => [...items, ...t].slice(0, 4));
        items.forEach(t => setTimeout(() => setToasts(ts => ts.filter(x => x.id !== t.id)), 12000));
        setFresh(new Set(added.map(a => a.id)));
        setTimeout(() => setFresh(new Set()), 2500);
      }
    }
    seenCrit.current = new Set(crit.map(a => a.id));
  }, [snap]);

  // Keep a valid selection when patients are discharged.
  useEffect(() => {
    if (snap && !snap.patients.some(p => p.id === selected)) setSelected(snap.patients[0]?.id ?? null);
  }, [snap, selected]);

  // Charge nurses land on the unit view.
  useEffect(() => { setView(user?.role === 'charge' ? 'unit' : 'patients'); setModal(null); }, [user?.username, user?.role]);

  const select = useCallback((pid: string) => {
    setSelected(pid);
    setView('patients');
    if (window.innerWidth < 760) document.querySelector('.detail')?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  const onGive = useCallback(async (pid: string, mid: string) => {
    try {
      const check = await api.checkAdministration(pid, mid);
      if (check.blocking.length) setModal({ kind: 'administer', pid, mid, check });
      else if (check.highAlert) setModal({ kind: 'double', pid, mid, check });
      else { const r = await api.giveMedication(pid, mid); if (!r.ok) notify(r.error || 'Could not give.'); }
    } catch { notify(NETWORK_ERROR); }
  }, [notify]);

  const close = useCallback(() => setModal(null), []);

  if (!user) return <Login />;
  if (!snap) return <div className="wrap"><div className="loading" role="status"><span className="spinner" aria-hidden="true" />Connecting to VitalHealth…</div></div>;

  const patient = snap.patients.find(p => p.id === selected);
  const mp = modal && 'pid' in modal && modal.pid ? snap.patients.find(p => p.id === modal.pid) : undefined;
  const mm = modal && 'mid' in modal && mp ? mp.meds.find(m => m.id === modal.mid) : undefined;

  return (
    <div className="wrap">
      <a className="skip" href="#main">Skip to {view === 'unit' ? 'unit overview' : 'patient details'}</a>
      {connection !== 'online' && (
        <div className="offline" role="alert">
          <b>{connection === 'offline' ? 'Connection lost. Reconnecting…' : 'Connecting…'}</b>
          <span>Showing the last data received ({fmt(snap.sim)}). Don't rely on this screen until it reconnects.</span>
        </div>
      )}
      <Header snap={snap} user={user} view={view} onView={setView} onAiControls={() => setModal({ kind: 'aictl' })} />
      {isDemoMode && <DemoControls snap={snap} onSelect={select} />}
      <div className="main">
        <PatientList snap={snap} selected={selected} onSelect={select} onAdmit={() => setModal({ kind: 'patient' })} />
        {view === 'unit' ? <UnitView snap={snap} onOpen={select} /> : <PatientPage snap={snap} patient={patient} fresh={fresh} actions={{
          onGive,
          onInfo: (pid, mid) => setModal({ kind: 'info', pid, mid }),
          onEdit: pid => setModal({ kind: 'patient', pid }),
          onDischarge: pid => setModal({ kind: 'discharge', pid }),
          onSbar: pid => setModal({ kind: 'sbar', pid }),
          onHandoff: pid => setModal({ kind: 'handoff', pid }),
        }} />}
        <aside className="feedcol">
          <AlertsFeed snap={snap} onOpenPatient={select} fresh={fresh} />
          <ActivityLog log={snap.log} />
          <section className="panel note">
            <b>How Vital works</b>
            <span>A rules engine re-checks every active order each time a vital, lab, order or patient detail changes. Critical alerts interrupt at administration, warnings stay in the panel, and low-priority checks are held back to reduce alert fatigue.</span>
            <span>Time-critical meds and care tasks count down and escalate if late. High-alert drugs need a second nurse to co-sign with an independently calculated dose. Tap ⓘ on any medication for drug info.</span>
            <span>The AI writes explanations and summaries only. It never calculates doses or makes the decision.</span>
          </section>
        </aside>
      </div>
      <p className="foot">{isDemoMode ? 'Demo mode: synthetic patients, simulated monitors. ' : ''}Not for clinical use. The nurse or provider always makes the final decision.</p>

      <Toasts items={toasts} onOpen={pid => select(pid)} onClose={id => setToasts(t => t.filter(x => x.id !== id))} />

      {modal?.kind === 'administer' && mp && mm && (
        <AdministerModal p={mp} m={mm} check={modal.check} onClose={close}
          onNeedsDoubleCheck={reason => setModal({ kind: 'double', pid: modal.pid, mid: modal.mid, check: modal.check, overrideReason: reason })} />
      )}
      {modal?.kind === 'double' && mp && mm && <DoubleCheckModal p={mp} m={mm} check={modal.check} overrideReason={modal.overrideReason} onClose={close} />}
      {modal?.kind === 'info' && mp && mm && <DrugInfoModal p={mp} m={mm} alerts={snap.alerts} sim={snap.sim} onClose={close} />}
      {modal?.kind === 'patient' && <PatientFormModal patient={mp} onClose={close} onSaved={id => { if (id) setSelected(id); close(); }} />}
      {(modal?.kind === 'sbar' || modal?.kind === 'handoff') && mp && <AiTextModal kind={modal.kind} p={mp} onClose={close} />}
      {modal?.kind === 'aictl' && <AiControlModal onClose={close} />}
      {modal?.kind === 'discharge' && mp && <DischargeModal p={mp} alerts={snap.alerts} onClose={close} onDone={close} />}
    </div>
  );
}

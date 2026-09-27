import type { Alert, Patient, Snapshot } from '../types';
import { crcl, roundVitals, sevRank } from '../engine/util';
import { COND } from '../engine/data';
import { AlertCard } from './AlertCard';
import { PatientStatus, Sparkline } from './ui';
import { MedicationTable } from './MedicationTable';
import { TimeCriticalPanel } from './TimeCriticalPanel';
import { NewMedCheck } from './NewMedCheck';
import { LabsTable } from './LabsTable';
import { can, whyNot } from '../engine/permissions';
import { useUser } from '../hooks/useSession';

export interface PatientActions {
  onGive: (pid: string, mid: string) => void;
  onInfo: (pid: string, mid: string) => void;
  onEdit: (pid: string) => void;
  onDischarge: (pid: string) => void;
  onSbar: (pid: string) => void;
  onHandoff: (pid: string) => void;
}

export function PatientPage({ snap, patient: p, actions, fresh }: { snap: Snapshot; patient: Patient | undefined; actions: PatientActions; fresh: Set<string> }) {
  if (!p) return <main className="detail" id="main"><section className="panel empty" style={{ padding: '40px 16px' }}><b>No patient selected</b>Admit a patient to start monitoring.</section></main>;
  const mine: Alert[] = snap.alerts.filter(a => a.pid === p.id).sort((a, b) => sevRank(a.sev) - sevRank(b.sev));
  return (
    <main className="detail" id="main" tabIndex={-1}>
      <PatientHeader snap={snap} p={p} actions={actions} />
      {mine.length > 0 && (
        <section className="panel section">
          <h3>Active alerts <span>{mine.length}</span></h3>
          {mine.map(a => <AlertCard key={a.id} alert={a} patient={p} full fresh={fresh.has(a.id)} />)}
        </section>
      )}
      <VitalsPanel p={p} />
      <MedicationTable snap={snap} p={p} onGive={actions.onGive} onInfo={actions.onInfo} />
      <TimeCriticalPanel sim={snap.sim} p={p} onGive={actions.onGive} />
      <NewMedCheck key={p.id} p={p} snap={snap} />
      <LabsTable sim={snap.sim} p={p} />
    </main>
  );
}

function PatientHeader({ snap, p, actions }: { snap: Snapshot; p: Patient; actions: PatientActions }) {
  const others = p.otherConds || [];
  const user = useUser();
  const canEdit = can(user, 'editPatient'), canDis = can(user, 'discharge');
  return (
    <section className="panel phead">
      <div className="phead-top">
        <div style={{ display: 'grid', gap: 4 }}>
          <h2>{p.name}</h2>
          <div className="meta">
            <span>Bed <b className="mono">{p.bed}</b></span>
            <span><b>{p.age}</b> y · {p.sex === 'F' ? 'Female' : 'Male'}</span>
            <span><b>{p.wt}</b> kg</span>
            <span>Est. CrCl <b className="mono">{crcl(p)}</b> mL/min</span>
          </div>
        </div>
        <div className="phbtns">
          <PatientStatus alerts={snap.alerts} pid={p.id} />
          <button className="btn sm primary" onClick={() => actions.onSbar(p.id)} title="Write an SBAR message to the provider">Notify provider</button>
          <button className="btn sm" onClick={() => actions.onHandoff(p.id)} title="Shift handoff summary">Handoff</button>
          <button className="btn sm" onClick={() => actions.onEdit(p.id)} disabled={!canEdit} title={canEdit ? 'Edit patient details' : whyNot('editPatient')}>Edit</button>
          <button className="btn sm" onClick={() => actions.onDischarge(p.id)} disabled={!canDis} title={canDis ? 'Discharge this patient' : whyNot('discharge')}>Discharge</button>
        </div>
      </div>
      <div className="meta"><span>{p.dx}</span></div>
      <div className="allergy">
        <span style={{ color: 'var(--muted)', fontWeight: 600 }}>Conditions:</span>
        {p.conditions.length || others.length
          ? <>{p.conditions.map(c => <span key={c} className="chip neutral">{COND[c]}</span>)}{others.map(c => <span key={c} className="chip neutral">{c}</span>)}</>
          : <span className="chip neutral">None recorded</span>}
        {canEdit && <button className="linkbtn" onClick={() => actions.onEdit(p.id)} aria-label="Edit conditions">Edit</button>}
      </div>
      <div className="allergy">
        <span style={{ color: 'var(--muted)', fontWeight: 600 }}>Allergies:</span>
        {p.allergies.length
          ? p.allergies.map((a, i) => <span key={i} className={`chip ${a.intol ? 'warn' : 'crit'}`}>{a.agent} · {a.rxn}</span>)
          : <span className="chip neutral">No known drug allergies</span>}
      </div>
    </section>
  );
}

function VitalsPanel({ p }: { p: Patient }) {
  const v = roundVitals(p.vit);
  const drop = Math.max(...p.hist.sbp.slice(-14)) - v.sbp;
  const bpS = v.sbp < 90 ? 'crit' : drop >= 22 ? 'warn' : '';
  const hrS = v.hr < 55 ? 'crit' : v.hr > 120 ? 'warn' : '';
  const rrS = v.rr < 12 ? 'crit' : v.rr > 24 ? 'warn' : '';
  const spS = v.spo2 < 90 ? 'crit' : v.spo2 < 93 ? 'warn' : '';
  const col = (s: string) => (s === 'crit' ? 'var(--crit)' : s === 'warn' ? 'var(--warn)' : 'var(--accent)');
  const Tile = ({ label, value, unit, s, data, lo, hi, thr }: { label: string; value: string | number; unit: string; s: string; data: number[]; lo: number; hi: number; thr: number }) => (
    <div className={`vt ${s}`}>
      <span className="lbl">{label}<span>{s === 'crit' ? 'LOW' : s === 'warn' ? 'WATCH' : ''}</span></span>
      <span className="val">{value}<small>{unit}</small></span>
      <Sparkline data={data} lo={lo} hi={hi} threshold={thr} color={col(s)} />
    </div>
  );
  return (
    <section className="panel section">
      <h3>Live vitals <span>bedside monitor · updates every few seconds</span></h3>
      <div className="vitals">
        <Tile label="Blood pressure" value={`${v.sbp}/${v.dbp}`} unit="mmHg" s={bpS} data={p.hist.sbp} lo={60} hi={170} thr={90} />
        <Tile label="Heart rate" value={v.hr} unit="bpm" s={hrS} data={p.hist.hr} lo={40} hi={140} thr={55} />
        <Tile label="Resp. rate" value={v.rr} unit="/min" s={rrS} data={p.hist.rr} lo={4} hi={30} thr={12} />
        <Tile label="SpO2" value={v.spo2} unit="%" s={spS} data={p.hist.spo2} lo={80} hi={100} thr={90} />
      </div>
    </section>
  );
}

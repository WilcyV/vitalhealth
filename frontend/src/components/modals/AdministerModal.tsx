import { useState } from 'react';
import type { AdministrationCheck, Medication, Patient } from '../../types';
import { api } from '../../api';
import { Modal } from './Modal';
import { Chip } from '../ui';
import { NETWORK_ERROR } from '../Notices';

const REASONS = ['Provider aware and ordered to give', 'Rechecked value is within range', 'Parameter does not apply (documented)', 'Other'];

interface Props { p: Patient; m: Medication; check: AdministrationCheck; onClose: () => void; onNeedsDoubleCheck: (overrideReason: string) => void }

/** "Stop and check" screen shown at Scan & give when Vital has alerts on this medication. */
export function AdministerModal({ p, m, check, onClose, onNeedsDoubleCheck }: Props) {
  const [showOvr, setShowOvr] = useState(false);
  const [reason, setReason] = useState('');
  const [note, setNote] = useState('');
  const [err, setErr] = useState('');
  const sev = check.blocking.some(a => a.sev === 'crit') ? 'crit' : 'warn';

  const hold = async () => {
    try { const r = await api.holdMedication(p.id, m.id, check.blocking[0]?.title || 'Nurse decision'); if (r.ok) onClose(); else setErr(r.error || 'Could not hold.'); }
    catch { setErr(NETWORK_ERROR); }
  };
  const confirmOverride = async () => {
    if (!reason || (reason === 'Other' && !note.trim())) { setErr(reason ? 'Add a note for "Other".' : 'Choose a reason.'); return; }
    const full = reason + (note.trim() ? ' — ' + note.trim() : '');
    if (check.highAlert) { onNeedsDoubleCheck(full); return; }
    try { const r = await api.giveMedication(p.id, m.id, { overrideReason: full }); if (r.ok) onClose(); else setErr(r.error || 'Could not give.'); }
    catch { setErr(NETWORK_ERROR); }
  };

  return (
    <Modal tone={sev} eyebrow={sev === 'crit' ? 'Vital · stop and check before giving' : 'Vital · review before giving'}
      title={`${m.name} ${m.dose} ${m.route} · ${p.bed} ${p.name}`} onClose={onClose}
      footer={<>
        <button className="btn" onClick={onClose}>Cancel</button>
        {showOvr ? <button className="btn" onClick={confirmOverride}>{check.highAlert ? 'Continue to double-check' : 'Confirm and give'}</button>
          : <button className="btn" onClick={() => setShowOvr(true)}>Give anyway…</button>}
        <button className={`btn ${sev === 'crit' ? 'danger' : 'primary'}`} onClick={hold} data-autofocus>Hold dose</button>
      </>}>
      {check.blocking.map(a => (
        <div key={a.id} className={`acard ${a.sev}`}>
          <div className="ah"><span className="at">{a.title}</span><Chip kind={a.sev}>{a.sev === 'crit' ? 'Critical' : 'Warning'}</Chip></div>
          <p>{a.why}</p>
          {a.data.length > 0 && <ul>{a.data.map((d, i) => <li key={i}>{d}</li>)}</ul>}
          <div className="act"><b>Suggested:</b> {a.action}</div>
        </div>
      ))}
      {showOvr && (
        <div className="ovr">
          <label htmlFor="ovrReason">Reason for giving anyway</label>
          <select id="ovrReason" value={reason} onChange={e => { setReason(e.target.value); setErr(''); }}>
            <option value="">Choose a reason</option>
            {REASONS.map(r => <option key={r}>{r}</option>)}
          </select>
          <label htmlFor="ovrNote">Note</label>
          <textarea id="ovrNote" value={note} onChange={e => setNote(e.target.value)} placeholder="Required for Other. Example: Dr. Patel notified at 09:05, said give." />
        </div>
      )}
      {err && <p className="dcerr">{err}</p>}
      <p className="decide">Vital is a second check. You make the call, and your decision is logged.</p>
    </Modal>
  );
}

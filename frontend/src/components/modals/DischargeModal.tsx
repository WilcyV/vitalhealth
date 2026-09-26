import { useState } from 'react';
import type { Alert, Patient } from '../../types';
import { api } from '../../api';
import { isActive } from '../../engine/util';
import { Modal } from './Modal';
import { NETWORK_ERROR } from '../Notices';

export function DischargeModal({ p, alerts, onClose, onDone }: { p: Patient; alerts: Alert[]; onClose: () => void; onDone: () => void }) {
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try { const r = await api.dischargePatient(p.id); if (r.ok) return onDone(); setErr(r.error || 'Could not discharge.'); }
    catch { setErr(NETWORK_ERROR); }
    setBusy(false);
  };
  const pending = p.meds.filter(isActive).length, al = alerts.filter(a => a.pid === p.id).length;
  return (
    <Modal eyebrow="Vital · Discharge" title={`Discharge ${p.name} from ${p.bed}?`} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn primary" data-autofocus onClick={go} disabled={busy}>{busy ? 'Discharging…' : 'Discharge patient'}</button></>}>
      <p style={{ margin: 0 }}>Vital stops monitoring this patient and bed {p.bed} becomes free.</p>
      {al || pending ? (
        <div className="verdict warn"><b>Before you discharge</b><span>{al ? `${al} active alert${al > 1 ? 's' : ''}. ` : ''}{pending ? `${pending} medication${pending > 1 ? 's' : ''} not yet given or held today.` : ''}</span></div>
      ) : (
        <div className="verdict ok"><b>Ready</b><span>No active alerts or pending medications.</span></div>
      )}
      {err && <p className="dcerr" role="alert">{err}</p>}
    </Modal>
  );
}

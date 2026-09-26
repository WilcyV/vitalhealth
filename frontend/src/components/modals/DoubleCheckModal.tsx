import { useEffect, useState } from 'react';
import type { AdministrationCheck, Medication, Patient, User } from '../../types';
import { api } from '../../api';
import { useUser } from '../../hooks/useSession';
import { NETWORK_ERROR } from '../Notices';
import { SLIDING_SCALE_TEXT } from '../../engine/doubleCheck';
import { crcl, highAlertReason, roundVitals } from '../../engine/util';
import { Modal } from './Modal';

interface Props { p: Patient; m: Medication; check: AdministrationCheck; overrideReason?: string; onClose: () => void }

/** Independent double-check for high-alert drugs (ISMP): a second nurse verifies and enters the dose they calculated. */
export function DoubleCheckModal({ p, m, check, overrideReason, onClose }: Props) {
  const items = [
    'Patient identity matches the wristband (name + date of birth)',
    `Drug matches the order: ${m.name}`,
    `Route: ${m.route}${m.route === 'IV' ? ' · line checked and patent' : ''}`,
    `Time: ${m.due === 'PRN' ? 'PRN · last dose and reason checked' : 'due ' + m.due}`,
    m.cls.includes('insulin') ? 'Latest glucose reviewed and meal tray confirmed'
      : m.cls.includes('anticoag') ? 'Latest INR / kidney function reviewed, no signs of bleeding'
      : m.cls.includes('opioid') ? 'Sedation level, respiratory rate and SpO2 reviewed' : 'Latest potassium reviewed',
  ];
  const [checked, setChecked] = useState<boolean[]>(items.map(() => false));
  const me = useUser();
  const [nurses, setNurses] = useState<User[]>([]);
  useEffect(() => { api.getUsers().then(us => setNurses(us.filter(u => (u.role === 'nurse' || u.role === 'charge') && u.username !== me?.username))).catch(() => setErr(NETWORK_ERROR)); }, [me?.username]);
  const [nurse, setNurse] = useState('');
  const [pin, setPin] = useState('');
  const [busy, setBusy] = useState(false);
  const [dose, setDose] = useState('');
  const [err, setErr] = useState('');
  const v = roundVitals(p.vit), unit = check.expected?.unit || '';

  const confirm = async () => {
    if (checked.some(c => !c)) return setErr('Check every item on the list before co-signing.');
    if (!nurse) return setErr('Choose the second nurse who is double-checking.');
    if (!pin) return setErr('The second nurse must enter their PIN.');
    if (dose === '') return setErr('The second nurse must enter the dose they calculated.');
    setBusy(true);
    try {
      const r = await api.giveMedication(p.id, m.id, { cosigner: nurse, cosignPin: pin, cosignDose: parseFloat(dose), overrideReason });
      if (r.ok) return onClose();
      setErr(r.error || 'Could not give.'); setPin('');
    } catch { setErr(NETWORK_ERROR); }
    setBusy(false);
  };

  return (
    <Modal tone="dc" eyebrow={`Vital · High-alert medication · ${highAlertReason(m)}`} title={`Independent double-check: ${m.name} · ${p.bed} ${p.name}`} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn primary" onClick={confirm} disabled={busy}>{busy ? 'Checking…' : 'Co-sign and give'}</button></>}>
      <p style={{ margin: 0 }}>High-alert drugs cause the most harm when there's a mistake. A second nurse signs in here with their own PIN and verifies the dose on their own before it can be given.</p>
      <div className="dcgrid">
        <span>Order</span><b>{m.name} {m.dose} · {m.route} · {m.freq}</b>
        <span>Patient</span><b>{p.name} · {p.age}{p.sex} · {p.wt} kg · {p.allergies.length ? p.allergies.map(a => a.agent + ' allergy').join(', ') : 'No known allergies'}</b>
        <span>Vitals / labs</span><b className="mono" style={{ fontWeight: 500 }}>BP {v.sbp}/{v.dbp} · RR {v.rr} · SpO2 {v.spo2}% · Glucose {p.labs.glu.v}{p.labs.inr ? ' · INR ' + p.labs.inr.v : ''} · CrCl {crcl(p)}</b>
      </div>
      <fieldset className="dccheck">
        <legend>Second nurse verifies</legend>
        {items.map((it, i) => (
          <label key={i}><input type="checkbox" checked={checked[i]} onChange={e => { const c = checked.slice(); c[i] = e.target.checked; setChecked(c); setErr(''); }} /> {it}</label>
        ))}
      </fieldset>
      <div className="ovr">
        <label htmlFor="dcNurse">Second nurse</label>
        <select id="dcNurse" value={nurse} onChange={e => { setNurse(e.target.value); setErr(''); }}>
          <option value="">Choose who is double-checking</option>
          {nurses.map(n => <option key={n.username} value={n.username}>{n.name}</option>)}
        </select>
        <label htmlFor="dcPin">Second nurse's PIN</label>
        <input id="dcPin" className="pin sm" type="password" inputMode="numeric" autoComplete="off" value={pin} onChange={e => { setPin(e.target.value); setErr(''); }} />
        <label htmlFor="dcDose">Dose calculated by the second nurse (without looking at yours)</label>
        <div className="dcdose"><input id="dcDose" type="number" step="any" inputMode="decimal" placeholder="Enter dose" value={dose} onChange={e => { setDose(e.target.value); setErr(''); }} /><span>{unit}</span></div>
        {m.cls.includes('insulin') && <details className="dcsc"><summary>Sliding scale for this order</summary><span className="mono">{SLIDING_SCALE_TEXT}</span></details>}
      </div>
      {err && <p className="dcerr">{err}</p>}
    </Modal>
  );
}

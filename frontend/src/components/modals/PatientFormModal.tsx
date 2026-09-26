import { useEffect, useState } from 'react';
import type { Allergy, Patient, PatientInput } from '../../types';
import { api } from '../../api';
import { ALLERGENS, COND } from '../../engine/data';
import { Modal } from './Modal';
import { NETWORK_ERROR } from '../Notices';

interface Row { agent: string; other: string; rxn: string; intol: boolean }

const toRow = (a: Allergy): Row => {
  const known = ALLERGENS.some(x => x.agent === a.agent);
  return { agent: known ? a.agent : 'Other', other: known ? '' : a.agent, rxn: a.rxn.replace(' (intolerance)', ''), intol: !!a.intol };
};

/** Admit a new patient, or edit name, age, gender, weight, bed, conditions and allergies. */
export function PatientFormModal({ patient, onClose, onSaved }: { patient?: Patient; onClose: () => void; onSaved: (pid?: string) => void }) {
  const edit = !!patient;
  const [name, setName] = useState(patient?.name || '');
  const [age, setAge] = useState(patient ? String(patient.age) : '');
  const [sex, setSex] = useState<'F' | 'M'>(patient?.sex || 'F');
  const [wt, setWt] = useState(patient ? String(patient.wt) : '70');
  const [bed, setBed] = useState(patient?.bed || '');
  const [dx, setDx] = useState(patient?.dx || '');
  const [conds, setConds] = useState<string[]>(patient?.conditions || []);
  const [other, setOther] = useState((patient?.otherConds || []).join(', '));
  const [rows, setRows] = useState<Row[]>((patient?.allergies || []).map(toRow));
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (!edit) api.suggestBed().then(setBed).catch(() => setErr(NETWORK_ERROR)); }, [edit]);

  const setRow = (i: number, patch: Partial<Row>) => { setRows(rows.map((r, n) => (n === i ? { ...r, ...patch } : r))); setErr(''); };

  const save = async () => {
    const allergies: Allergy[] = rows.map(r => {
      const def = ALLERGENS.find(x => x.agent === r.agent)!;
      const agent = r.agent === 'Other' ? r.other.trim() : r.agent;
      return { agent, cls: r.agent === 'Other' ? 'other' : def.cls, rxn: (r.rxn.trim() || 'reaction not recorded') + (r.intol ? ' (intolerance)' : ''), intol: r.intol };
    });
    const input: PatientInput = {
      name, age: parseInt(age, 10), sex, wt: parseFloat(wt), bed: bed.trim().toUpperCase(), dx, conditions: conds,
      otherConds: other.split(',').map(x => x.trim()).filter(Boolean), allergies,
    };
    setBusy(true);
    try {
      const r = edit ? await api.updatePatient(patient!.id, input) : await api.admitPatient(input);
      if (r.ok) return onSaved(r.id);
      setErr(r.error || 'Could not save.');
    } catch { setErr(NETWORK_ERROR); }
    setBusy(false);
  };

  return (
    <Modal eyebrow={`Vital · ${edit ? 'Edit patient' : 'Admit patient'}`} title={edit ? patient!.name : 'New patient'} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn primary" onClick={save} disabled={busy}>{busy ? 'Saving…' : edit ? 'Save changes' : 'Admit patient'}</button></>}>
      <form className="pform" noValidate onSubmit={e => { e.preventDefault(); save(); }} onChange={() => setErr('')}>
        <label className="full">Full name<input type="text" autoComplete="off" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Carmen Díaz" /></label>
        <label>Age<input type="number" min={0} max={120} value={age} onChange={e => setAge(e.target.value)} placeholder="years" /></label>
        <label>Gender<select value={sex} onChange={e => setSex(e.target.value as 'F' | 'M')}><option value="F">Female</option><option value="M">Male</option></select></label>
        <label>Weight (kg)<input type="number" min={1} max={400} step={0.1} value={wt} onChange={e => setWt(e.target.value)} /></label>
        <label>Bed
          <span className="bedrow">
            <input type="text" maxLength={4} value={bed} onChange={e => setBed(e.target.value.toUpperCase())} aria-label="Bed" />
            <button type="button" className="btn" onClick={() => api.suggestBed(patient?.id).then(setBed).catch(() => setErr(NETWORK_ERROR))} title="Assign a random free bed">Random</button>
          </span>
        </label>
        <label className="full">Reason for admission<input type="text" value={dx} onChange={e => setDx(e.target.value)} placeholder="e.g. Community-acquired pneumonia" /></label>
        <fieldset className="full conds">
          <legend>Conditions Vital should check against</legend>
          {Object.keys(COND).map(k => (
            <label key={k}><input type="checkbox" checked={conds.includes(k)} onChange={e => setConds(e.target.checked ? [...conds, k] : conds.filter(c => c !== k))} /> {COND[k]}</label>
          ))}
          <label className="full" style={{ gridColumn: '1/-1' }}>Other conditions (comma-separated)<input type="text" value={other} onChange={e => setOther(e.target.value)} placeholder="e.g. COPD, hypothyroidism" /></label>
        </fieldset>
        <fieldset className="full algs">
          <legend>Allergies</legend>
          <div id="algList">
            {rows.map((r, i) => (
              <div className="algrow" key={i}>
                <select aria-label="Allergen" value={r.agent} onChange={e => setRow(i, { agent: e.target.value })}>{ALLERGENS.map(x => <option key={x.agent}>{x.agent}</option>)}</select>
                {r.agent === 'Other' && <input className="alg-other" type="text" placeholder="Allergen name" aria-label="Other allergen" value={r.other} onChange={e => setRow(i, { other: e.target.value })} />}
                <input type="text" placeholder="Reaction (e.g. hives)" aria-label="Reaction" value={r.rxn} onChange={e => setRow(i, { rxn: e.target.value })} />
                <select aria-label="Type" value={r.intol ? 'intol' : 'allergy'} onChange={e => setRow(i, { intol: e.target.value === 'intol' })}><option value="allergy">Allergy</option><option value="intol">Intolerance</option></select>
                <button type="button" className="btn icon" aria-label="Remove allergy" onClick={() => setRows(rows.filter((_, n) => n !== i))}>×</button>
              </div>
            ))}
          </div>
          {rows.length === 0 && <p className="algnone">No known drug allergies.</p>}
          <button type="button" className="btn" onClick={() => setRows([...rows, { agent: ALLERGENS[0].agent, other: '', rxn: '', intol: false }])}>+ Add allergy</button>
        </fieldset>
        {err && <p className="dcerr full" role="alert">{err}</p>}
        <button type="submit" hidden />
      </form>
    </Modal>
  );
}

import { useEffect, useMemo, useRef, useState } from 'react';
import type { Alternative, CatalogDrug, CheckIssue, Patient, Snapshot } from '../types';
import { crcl, firstName, roundVitals } from '../engine/util';
import { GROUP_LABEL } from '../engine/data';
import { can, whyNot } from '../engine/permissions';
import { api } from '../api';
import { useUser } from '../hooks/useSession';
import { NETWORK_ERROR } from './Notices';

const REASONS = ['Benefit outweighs risk, discussed with pharmacy', 'Allergy history reviewed, tolerated before', 'Will monitor closely'];
const display = (d: CatalogDrug) => d.tall || d.name;

/** "Check a new medication": search with tall-man lettering, live verdict, safer alternatives, look-alike confirmation. */
export function NewMedCheck({ p, snap }: { p: Patient; snap: Snapshot }) {
  const user = useUser();
  const canOrder = can(user, 'order');
  const [catalog, setCatalog] = useState<CatalogDrug[] | null>(null);
  const [loadErr, setLoadErr] = useState('');
  const [key, setKey] = useState('');
  const [issues, setIssues] = useState<CheckIssue[] | null>(null);
  const [alts, setAlts] = useState<Alternative[]>([]);
  const [checking, setChecking] = useState(false);
  const [ovr, setOvr] = useState(false);
  const [reason, setReason] = useState('');
  const [lasaOk, setLasaOk] = useState(false);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.getCatalog().then(setCatalog).catch(() => setLoadErr(NETWORK_ERROR)); }, []);

  // Re-run the check whenever the patient's data changes, so the verdict stays live.
  useEffect(() => {
    let alive = true;
    if (!key) { setIssues(null); setAlts([]); return; }
    Promise.all([api.checkMedication(p.id, key), api.suggestAlternatives(p.id, key)])
      .then(([r, a]) => { if (alive) { setIssues(r); setAlts(a); setChecking(false); } })
      .catch(() => { if (alive) { setErr(NETWORK_ERROR); setChecking(false); } });
    return () => { alive = false; };
  }, [key, p.id, snap]);

  const choose = (k: string) => { setKey(k); setChecking(!!k); setIssues(null); setOvr(false); setReason(''); setLasaOk(false); setErr(''); };
  const reset = () => choose('');
  const order = async (overrideReason?: string) => {
    setBusy(true);
    try {
      const r = await api.orderMedication(p.id, key, overrideReason);
      if (r.ok) reset(); else setErr(r.error || 'Could not place the order.');
    } catch { setErr(NETWORK_ERROR); }
    setBusy(false);
  };

  const d = catalog?.find(x => x.key === key);
  const twin = d?.lasa ? catalog?.find(x => x.key === d.lasa) : undefined;
  const nc = issues?.filter(i => i.sev === 'crit').length || 0, nw = issues?.filter(i => i.sev === 'warn').length || 0;
  const verdict = nc ? 'crit' : nw ? 'warn' : 'ok';
  const v = roundVitals(p.vit), L = p.labs;
  const needLasa = !!twin && !lasaOk;

  return (
    <section className="panel section ck" aria-labelledby="ck-h">
      <h3 id="ck-h">Check a new medication <span>before it's ordered</span></h3>
      <p className="ckl">Vital compares it with {firstName(p)}'s current medications, conditions, allergies, labs and vitals.</p>
      {loadErr ? <p className="dcerr">{loadErr}</p> : !catalog ? <p className="muted">Loading medications…</p> : (
        <DrugPicker catalog={catalog} value={key} onChange={choose} />
      )}
      {!canOrder && <p className="muted small">{whyNot('order')} You can still check any medication.</p>}
      {d && (checking || !issues) && <p className="muted">Checking…</p>}
      {d && issues && !checking && (
        <div id="d-check-res">
          {twin && (
            <div className="lasa" role="alert">
              <b>Look-alike name: {display(d)} vs {display(twin)}</b>
              <span>You chose <b>{display(d)}</b>, a {d.purpose}. It is often confused with <b>{display(twin)}</b>, a {twin.purpose}.</span>
              <label><input type="checkbox" checked={lasaOk} onChange={e => setLasaOk(e.target.checked)} /> I confirm I mean {display(d)} ({d.purpose}).</label>
            </div>
          )}
          <div className={`verdict ${verdict}`}>
            <b>{nc ? 'Not compatible' : nw ? 'Use with caution' : 'Compatible'}: {display(d)} {d.dose} {d.route}</b>
            <span>{nc ? `${nc} critical issue${nc > 1 ? 's' : ''}${nw ? ` and ${nw} warning${nw > 1 ? 's' : ''}` : ''} for ${firstName(p)}.` : nw ? `${nw} thing${nw > 1 ? 's' : ''} to review before ordering.` : `No problems found for ${firstName(p)}.`}</span>
          </div>
          <p className="ckmeta mono">
            Checked against {p.meds.length} medications · {p.conditions.length + (p.otherConds?.length || 0)} conditions · {p.allergies.length ? p.allergies.map(a => a.agent).join(', ') + ' allergy' : 'no known allergies'} · K+ {L.k.v}, CrCl {crcl(p)}, glucose {L.glu.v}{L.inr ? `, INR ${L.inr.v}` : ''} · BP {v.sbp}/{v.dbp}, HR {v.hr}, SpO2 {v.spo2}%
          </p>
          {issues.map((i, n) => (
            <article key={n} className={`acard ${i.sev}`}>
              <div className="ah"><span className="at">{i.title}</span><span className={`chip ${i.sev}`}>{i.type}</span></div>
              <p>{i.why}</p>
              <div className="act"><b>Suggested:</b> {i.action}</div>
            </article>
          ))}
          {nc > 0 && (
            <div className="alts">
              <b>Safer options for {GROUP_LABEL[d.group] || 'this need'}</b>
              {alts.length === 0 ? <span className="muted small">No option in the catalog passes every check for {firstName(p)}. Ask pharmacy.</span> : alts.map(a => {
                const w = a.issues.filter(i => i.sev === 'warn').length;
                return (
                  <div key={a.drug.key} className="alt">
                    <span><b>{display(a.drug)}</b> {a.drug.dose} {a.drug.route} · {a.drug.freq}</span>
                    <span className={`chip ${w ? 'warn' : 'ok'}`}>{w ? `${w} to review` : 'Passes all checks'}</span>
                    <button className="btn sm" onClick={() => choose(a.drug.key)}>Check this instead</button>
                  </div>
                );
              })}
            </div>
          )}
          {err && <p className="dcerr">{err}</p>}
          <div className="ckbtns">
            {nc ? (ovr ? (
              <div className="ovr" style={{ width: '100%' }}>
                <label htmlFor="ckReason">Reason for ordering anyway</label>
                <select id="ckReason" value={reason} onChange={e => { setReason(e.target.value); setErr(''); }}>
                  <option value="">Choose a reason</option>
                  {REASONS.map(r => <option key={r}>{r}</option>)}
                </select>
                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  <button className="btn" onClick={reset}>Don't order</button>
                  <button className="btn danger" disabled={busy || needLasa} onClick={() => reason ? order(reason) : setErr('Choose a reason to order anyway.')}>{busy ? 'Ordering…' : 'Confirm order'}</button>
                </div>
              </div>
            ) : (
              <>
                <button className="btn" onClick={() => setOvr(true)} disabled={!canOrder} title={canOrder ? undefined : whyNot('order')}>Order anyway…</button>
                <button className="btn primary" onClick={reset}>Don't order</button>
              </>
            )) : (
              <>
                <button className="btn" onClick={reset}>Cancel</button>
                <button className="btn primary" onClick={() => order()} disabled={!canOrder || busy || needLasa}
                  title={!canOrder ? whyNot('order') : needLasa ? 'Confirm the look-alike name first' : undefined}>{busy ? 'Ordering…' : 'Add order'}</button>
              </>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

/** Accessible search-as-you-type drug picker (combobox pattern). */
function DrugPicker({ catalog, value, onChange }: { catalog: CatalogDrug[]; value: string; onChange: (key: string) => void }) {
  const selected = catalog.find(d => d.key === value);
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);
  useEffect(() => { setQ(selected ? `${display(selected)} ${selected.dose} ${selected.route}` : ''); }, [value]);
  const matches = useMemo(() => {
    const t = q.trim().toLowerCase();
    const all = t && !(selected && q.startsWith(display(selected))) ? catalog.filter(d => d.name.toLowerCase().includes(t) || (GROUP_LABEL[d.group] || '').includes(t)) : catalog;
    return all.slice(0, 40);
  }, [q, catalog, selected]);
  const pick = (d: CatalogDrug) => { onChange(d.key); setOpen(false); };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setHi(h => Math.min(matches.length - 1, h + 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHi(h => Math.max(0, h - 1)); }
    else if (e.key === 'Enter' && open && matches[hi]) { e.preventDefault(); pick(matches[hi]); }
    else if (e.key === 'Escape') setOpen(false);
  };
  useEffect(() => { listRef.current?.querySelector<HTMLElement>(`[data-i="${hi}"]`)?.scrollIntoView({ block: 'nearest' }); }, [hi]);
  return (
    <div className="picker">
      <input id="ckDrug" type="text" role="combobox" aria-expanded={open} aria-controls="ckList" aria-autocomplete="list" autoComplete="off"
        aria-activedescendant={open && matches[hi] ? `opt-${matches[hi].key}` : undefined} aria-label="Search a medication"
        placeholder="Search a medication (e.g. ibuprofen, hydr…)" value={q}
        onChange={e => { setQ(e.target.value); setOpen(true); setHi(0); if (value) onChange(''); }}
        onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)} onKeyDown={onKey} />
      {open && (
        <ul id="ckList" role="listbox" ref={listRef} className="plist-drop">
          {matches.length === 0 && <li className="muted small" role="option" aria-disabled="true" aria-selected={false}>No matches</li>}
          {matches.map((d, i) => (
            <li key={d.key} id={`opt-${d.key}`} data-i={i} role="option" aria-selected={i === hi} className={i === hi ? 'on' : ''}
              onMouseDown={e => { e.preventDefault(); pick(d); }} onMouseEnter={() => setHi(i)}>
              <b>{display(d)}</b> {d.dose} {d.route} · <span className="muted">{d.freq}</span>{d.lasa && <span className="chip warn tiny">look-alike</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

import { useEffect, useState } from 'react';
import type { AiUsage } from '../../types';
import { api } from '../../api';
import { Modal } from './Modal';
import { NETWORK_ERROR } from '../Notices';
import { REASON_LABEL, money } from '../../engine/aiControl';

/** Take control of AI: on/off switch, privacy promise, recent requests. */
export function AiControlModal({ onClose }: { onClose: () => void }) {
  const [u, setU] = useState<AiUsage | null>(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const load = () => api.getAiUsage().then(setU).catch(() => setErr(NETWORK_ERROR));
  useEffect(() => { load(); }, []);

  const save = async (s: { mode?: 'on' | 'off' }) => {
    setBusy(true); setErr('');
    try { const r = await api.setAiSettings(s); if (r.ok && r.usage) setU(r.usage); else setErr(r.error || 'Could not save.'); }
    catch { setErr(NETWORK_ERROR); }
    setBusy(false);
  };

  return (
    <Modal eyebrow="Vital AI · Take control" title="AI controls" onClose={onClose}
      footer={<button className="btn" onClick={onClose}>Close</button>}>
      {!u && !err && <div className="loading" role="status"><span className="spinner" aria-hidden="true" />Loading…</div>}
      {u && (
        <div className="aictl">
          <section>
            <div className="aictl-row">
              <div>
                <b>Use AI to rewrite messages</b>
                <p className="muted small">{u.mode === 'on' ? 'On: SBAR and handoff wording is polished by AI. Safety decisions never use AI.' : 'Off: Vital uses its templates. Nothing is sent to any AI.'}</p>
              </div>
              <button role="switch" aria-checked={u.mode === 'on'} aria-label="Use AI" className={`switch ${u.mode === 'on' ? 'on' : ''}`} disabled={busy}
                onClick={() => save({ mode: u.mode === 'on' ? 'off' : 'on' })}><span /></button>
            </div>
            {!u.keyConfigured && <p className="muted small">No AI key on this server, so every message uses the template. The panel still shows what would be sent and what it would cost.</p>}
          </section>

          <section>
            <h4>Privacy</h4>
            <ul className="small aictl-list">
              <li>Patient <b>name and bed are removed</b> before any text leaves the hospital, and ages over 89 become "90+".</li>
              <li>The AI only sees the de-identified message. Real values are put back on your screen only.</li>
              <li>The AI never decides: alerts, holds and the medication check come from Vital's rules, not the model.</li>
              <li>Every AI rewrite is checked; if it changes a number, drug or action, it is blocked. <b>{u.blocked}</b> blocked so far.</li>
            </ul>
          </section>

          <section>
            <h4>Recent AI requests</h4>
            {u.recent.length === 0 ? <p className="muted small">None yet. Open "Notify provider" or "Handoff" on a patient.</p> : (
              <table className="aictl-table small">
                <thead><tr><th>Text</th><th>Result</th><th>Tokens</th><th>Cost</th></tr></thead>
                <tbody>{u.recent.map((r, i) => (
                  <tr key={i}><td>{r.kind.toUpperCase()}{r.deidentified ? ' · de-identified' : ''}</td><td>{REASON_LABEL[r.reason]}</td><td className="mono">{r.tokens}</td><td className="mono">{money(r.costUsd)}</td></tr>
                ))}</tbody>
              </table>
            )}
          </section>
        </div>
      )}
      {err && <p className="dcerr" role="alert">{err}</p>}
    </Modal>
  );
}

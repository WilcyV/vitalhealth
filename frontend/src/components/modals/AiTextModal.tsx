import { useEffect, useRef, useState } from 'react';
import type { AiText, Patient } from '../../types';
import { api } from '../../api';
import { Modal } from './Modal';
import { NETWORK_ERROR } from '../Notices';

/** Shows text written by Vital AI: the SBAR message to the provider, or the shift handoff. */
export function AiTextModal({ kind, p, onClose }: { kind: 'sbar' | 'handoff'; p: Patient; onClose: () => void }) {
  const [data, setData] = useState<AiText | null>(null);
  const [text, setText] = useState('');
  const [err, setErr] = useState('');
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const area = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    let alive = true;
    (kind === 'sbar' ? api.getSbar(p.id) : api.getHandoff(p.id))
      .then(r => { if (alive) { setData(r); setText(r.text); } })
      .catch(() => alive && setErr(NETWORK_ERROR));
    return () => { alive = false; };
  }, [kind, p.id]);

  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); }
    catch { area.current?.select(); setErr('Copy isn’t available here. The text is selected: press Cmd+C (Ctrl+C).'); }
  };
  const send = async () => {
    setBusy(true);
    try { const r = await api.sendSbar(p.id, text); if (r.ok) return onClose(); setErr(r.error || 'Could not send.'); }
    catch { setErr(NETWORK_ERROR); }
    setBusy(false);
  };

  const title = kind === 'sbar' ? `Notify provider · ${p.bed} ${p.name}` : `Shift handoff · ${p.bed} ${p.name}`;
  return (
    <Modal eyebrow={kind === 'sbar' ? 'Vital AI · SBAR message' : 'Vital AI · Handoff summary'} title={title} onClose={onClose}
      footer={<>
        <button className="btn" onClick={onClose}>Close</button>
        <button className="btn" onClick={copy} disabled={!data}>{copied ? 'Copied' : 'Copy'}</button>
        {kind === 'sbar' && <button className="btn primary" onClick={send} disabled={!data || busy || !text.trim()}>{busy ? 'Sending…' : 'Mark as sent'}</button>}
      </>}>
      {!data && !err && <div className="loading" role="status"><span className="spinner" aria-hidden="true" />Writing…</div>}
      {data && (
        <>
          <p className="muted small" style={{ margin: 0 }}>
            <span className={`chip ${data.source === 'ai' ? 'info' : 'neutral'}`}>{data.source === 'ai' ? 'Written by Vital AI' : 'Template (AI off)'}</span>{' '}
            {kind === 'sbar' ? 'Situation · Background · Assessment · Recommendation. Review and edit before sending.' : 'Review before handing off.'}
          </p>
          <label className="sr" htmlFor="aiText">{kind === 'sbar' ? 'SBAR message' : 'Handoff summary'}</label>
          <textarea id="aiText" ref={area} className="aitext" value={text} onChange={e => setText(e.target.value)} rows={kind === 'sbar' ? 9 : 6} />
          <p className="decide">The facts come from Vital's rules. The AI only rewrites the wording and is blocked from changing any number, drug or recommendation.</p>
        </>
      )}
      {err && <p className="dcerr" role="alert">{err}</p>}
    </Modal>
  );
}

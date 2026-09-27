import type { AiDetails } from '../types';
import { REASON_LABEL, money } from '../engine/aiControl';

/** "What did Vital send to the AI?" Privacy + cost for one request (Assurant: Take Control of AI). */
export function AiTransparency({ d }: { d: AiDetails }) {
  const sent = d.reason === 'ai' || d.reason === 'guard' || d.reason === 'error';
  const tokens = d.tokensIn + d.tokensOut;
  const wouldCost = d.costUsd || (d.tokensIn * 3 + 250 * 15) / 1e6; // estimate with a ~250-token answer
  return (
    <details className="aitx">
      <summary>
        <b>AI transparency</b>
        <span className={`chip ${d.reason === 'ai' ? 'info' : 'neutral'}`}>{REASON_LABEL[d.reason]}</span>
        {d.deidentified && <span className="chip ok">Patient de-identified</span>}
      </summary>
      <div className="aitx-body">
        <p className="small">
          {sent ? 'This is exactly what left the hospital:' : 'Nothing left the hospital. If AI were on, this is exactly what would be sent:'}
          {d.removed.length > 0 && <> Vital removed the patient's <b>{d.removed.join(', ')}</b> first and puts them back only on this screen.</>}
        </p>
        <pre className="aitx-sent mono" aria-label="Text sent to the AI">{d.sentText}</pre>
        <dl className="aitx-kv">
          <div><dt>Model</dt><dd className="mono">{d.model}</dd></div>
          <div><dt>Tokens</dt><dd className="mono">{d.tokensIn} in · {d.tokensOut} out{d.estimated ? ' (est.)' : ''}</dd></div>
          <div><dt>{d.reason === 'ai' ? 'Cost' : 'Cost if sent'}</dt><dd className="mono">{d.reason === 'ai' ? money(d.costUsd) : `~${money(wouldCost)} · this time $0`}</dd></div>
          <div><dt>Tokens total</dt><dd className="mono">{tokens}</dd></div>
        </dl>
      </div>
    </details>
  );
}

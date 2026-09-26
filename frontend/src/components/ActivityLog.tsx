import type { LogEntry } from '../types';
import { fmt } from '../engine/util';

export function ActivityLog({ log }: { log: LogEntry[] }) {
  return (
    <section className="panel">
      <div className="panel-h"><h2>Activity log</h2></div>
      <div className="log">
        {log.slice(0, 30).map((l, i) => {
          const cut = l.text.indexOf(' · ');
          return (
            <div key={i}>
              <span className="mono">{fmt(l.t)}</span>
              <span className={`k-${l.kind}`}>{cut > 0 ? <><b className="lp">{l.text.slice(0, cut)}</b> · {l.text.slice(cut + 3)}</> : l.text}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

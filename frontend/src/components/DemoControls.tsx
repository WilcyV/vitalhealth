import type { Snapshot } from '../types';
import { api } from '../api';
import { AsyncButton } from './AsyncButton';

export function DemoControls({ snap, onSelect }: { snap: Snapshot; onSelect: (pid: string) => void }) {
  return (
    <section className="controls" aria-label="Demo events">
      <div className="controls-head">
        <h2>Demo · inject an event</h2>
        <p>Each button changes a lab, vital, or order. Click it again to undo.</p>
        <AsyncButton action={() => api.resetDemo()}>Reset demo</AsyncButton>
      </div>
      <div className="scen">
        {snap.scenarios.map(s => (
          <AsyncButton key={s.key} className={s.used ? 'used' : ''} title={s.used ? 'Click to undo' : 'Click to trigger'}
            action={() => { onSelect(s.pid); return api.triggerScenario(s.key); }}>
            <b>{s.label}</b><span>{s.used ? '↺ Click to undo' : s.patientLabel}</span>
          </AsyncButton>
        ))}
      </div>
    </section>
  );
}

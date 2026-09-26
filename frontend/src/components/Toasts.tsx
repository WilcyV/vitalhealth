export interface ToastItem { id: string; pid: string; eyebrow: string; title: string; sub: string }

export function Toasts({ items, onOpen, onClose }: { items: ToastItem[]; onOpen: (pid: string) => void; onClose: (id: string) => void }) {
  return (
    <div className="toasts" aria-live="polite">
      {items.map(t => (
        <div key={t.id} className="toast" role="button" tabIndex={0} onClick={() => onOpen(t.pid)} onKeyDown={e => { if (e.key === 'Enter') onOpen(t.pid); }}>
          <span className="eyebrow">{t.eyebrow}</span>
          <b>{t.title}</b>
          <span>{t.sub}</span>
          <button className="tx" aria-label="Dismiss notification" onClick={e => { e.stopPropagation(); onClose(t.id); }}>×</button>
        </div>
      ))}
    </div>
  );
}

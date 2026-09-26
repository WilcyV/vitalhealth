import { createContext, useCallback, useContext, useState } from 'react';

type Kind = 'error' | 'info';
interface Notice { id: number; text: string; kind: Kind }
const Ctx = createContext<(text: string, kind?: Kind) => void>(() => {});

export const NETWORK_ERROR = 'Couldn’t reach the VitalHealth server. Nothing was saved. Check the connection and try again.';

/** App-wide status messages for failed actions (network errors, permission problems). */
export function NoticeProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Notice[]>([]);
  const notify = useCallback((text: string, kind: Kind = 'error') => {
    const id = Date.now() + Math.random();
    setItems(n => [...n.filter(x => x.text !== text), { id, text, kind }].slice(-3));
    setTimeout(() => setItems(n => n.filter(x => x.id !== id)), 7000);
  }, []);
  return (
    <Ctx.Provider value={notify}>
      {children}
      <div className="notices" role="status" aria-live="assertive">
        {items.map(n => (
          <div key={n.id} className={`notice ${n.kind}`}>
            <span>{n.text}</span>
            <button className="tx" aria-label="Dismiss message" onClick={() => setItems(x => x.filter(i => i.id !== n.id))}>×</button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export const useNotify = () => useContext(Ctx);

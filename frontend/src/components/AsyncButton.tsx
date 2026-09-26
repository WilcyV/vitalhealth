import { useEffect, useRef, useState } from 'react';
import type { Permission } from '../types';
import { can, whyNot } from '../engine/permissions';
import { useUser } from '../hooks/useSession';
import { NETWORK_ERROR, useNotify } from './Notices';

interface Props extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'onClick'> {
  /** Runs the API call. A `{ ok: false, error }` result is shown to the user. */
  action: () => Promise<unknown> | unknown;
  /** Disable (with an explanation) when the signed-in user lacks this permission. */
  perm?: Permission;
  busyLabel?: string;
}

/** Button with a busy state, error handling and role-based disabling. */
export function AsyncButton({ action, perm, busyLabel, children, disabled, title, className = 'btn', ...rest }: Props) {
  const user = useUser();
  const notify = useNotify();
  const [busy, setBusy] = useState(false);
  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);
  const allowed = !perm || can(user, perm);
  const onClick = async () => {
    setBusy(true);
    try {
      const r = await action();
      if (r && typeof r === 'object' && 'ok' in r && (r as { ok: boolean }).ok === false) notify((r as { error?: string }).error || 'That didn’t work. Try again.');
    } catch {
      notify(NETWORK_ERROR);
    } finally {
      if (mounted.current) setBusy(false);
    }
  };
  return (
    <button {...rest} className={className} disabled={disabled || busy || !allowed} aria-busy={busy}
      title={!allowed && perm ? whyNot(perm) : title} onClick={onClick}>
      {busy && busyLabel ? busyLabel : children}
    </button>
  );
}

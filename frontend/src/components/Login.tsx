import { useEffect, useState } from 'react';
import type { User } from '../types';
import { api, isDemoMode } from '../api';
import { ROLE_LABEL } from '../engine/permissions';
import { NETWORK_ERROR } from './Notices';

export function Login() {
  const [users, setUsers] = useState<User[] | null>(null);
  const [loadErr, setLoadErr] = useState('');
  const [who, setWho] = useState('');
  const [pin, setPin] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.getUsers().then(setUsers).catch(() => setLoadErr(NETWORK_ERROR)); }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!who) return setErr('Choose your name.');
    if (!pin) return setErr('Enter your PIN.');
    setBusy(true); setErr('');
    try {
      const r = await api.login(who, pin);
      if (!r.ok) { setErr(r.error || 'Sign-in failed.'); setPin(''); }
    } catch { setErr(NETWORK_ERROR); }
    setBusy(false);
  };

  return (
    <main className="login">
      <form className="panel login-card" onSubmit={submit} noValidate>
        <div className="brand">
          <div className="mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="var(--accent-ink)" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round"><path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3z" /><path d="M8 12.5h2l1.2-2.5 1.8 4.5 1.2-2H16" /></svg>
          </div>
          <div><h1>VitalHealth</h1><small>4 West · Med-Surg</small></div>
        </div>
        <h2>Sign in</h2>
        {loadErr && <p className="dcerr">{loadErr}</p>}
        {!users && !loadErr && <p className="muted">Loading staff list…</p>}
        {users && (
          <fieldset className="who">
            <legend>Who's signing in?</legend>
            {users.map(u => (
              <label key={u.username} className={`whoopt ${who === u.username ? 'sel' : ''}`}>
                <input type="radio" name="who" value={u.username} checked={who === u.username} onChange={() => { setWho(u.username); setErr(''); }} />
                <b>{u.name}</b><span>{ROLE_LABEL[u.role]}</span>
              </label>
            ))}
          </fieldset>
        )}
        <label className="pinl" htmlFor="pin">PIN</label>
        <input id="pin" className="pin" type="password" inputMode="numeric" autoComplete="off" maxLength={8} value={pin} onChange={e => { setPin(e.target.value); setErr(''); }} />
        {err && <p className="dcerr">{err}</p>}
        <button className="btn primary" type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        {isDemoMode && <p className="muted small">Demo mode: every account's PIN is <b className="mono">1234</b>. In the hospital this is replaced by single sign-on and a badge tap.</p>}
      </form>
    </main>
  );
}

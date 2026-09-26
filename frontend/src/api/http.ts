// Client for the FastAPI backend. Enable it by setting VITE_API_URL (see .env.example).
// The server pushes a full Snapshot over the WebSocket every time state changes,
// and every action below is a plain REST call. The contract is documented in README.md.
import type {
  AdministrationCheck, Alternative, CatalogDrug, CheckIssue, Connection, DrugInfo, GiveOptions, LoginResult, PatientInput, Result, Snapshot, User,
} from '../types';
import type { VitalApi } from './index';

export class HttpApi implements VitalApi {
  private snapshot: Snapshot | null = null;
  private listeners = new Set<() => void>();
  private ws: WebSocket | null = null;
  private retry = 0;
  private connection: Connection = 'connecting';
  private user: User | null = null;

  constructor(private base: string) { this.base = base.replace(/\/$/, ''); }

  start() { this.connect(); }

  private connect() {
    const url = this.base.replace(/^http/, 'ws') + '/ws';
    this.ws = new WebSocket(url);
    this.ws.onopen = () => { this.setConnection('online'); };
    this.ws.onmessage = ev => {
      this.snapshot = JSON.parse(ev.data) as Snapshot;
      this.retry = 0;
      this.listeners.forEach(l => l());
    };
    this.ws.onclose = () => {
      this.setConnection(this.snapshot ? 'offline' : 'connecting');
      // reconnect with backoff (max 10 s)
      const wait = Math.min(10000, 500 * 2 ** this.retry++);
      setTimeout(() => this.connect(), wait);
    };
  }

  private setConnection(c: Connection) { if (c !== this.connection) { this.connection = c; this.listeners.forEach(l => l()); } }
  getConnection() { return this.connection; }

  getUsers() { return this.req<User[]>('GET', '/api/auth/users'); }
  async login(username: string, pin: string) {
    const r = await this.req<LoginResult>('POST', '/api/auth/login', { username, pin });
    if (r.ok && r.user) { this.user = r.user; this.listeners.forEach(l => l()); }
    return r;
  }
  async logout() { await this.req('POST', '/api/auth/logout'); this.user = null; this.listeners.forEach(l => l()); }
  getUser() { return this.user; }

  subscribe(listener: () => void) { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; }
  getSnapshot() { return this.snapshot; }

  private async req<T>(method: string, path: string, body?: unknown): Promise<T> {
    const res = await fetch(this.base + path, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      credentials: 'include', // session cookie from hospital SSO
    });
    if (res.status === 401) { this.user = null; this.listeners.forEach(l => l()); return { ok: false, error: 'Your session ended. Sign in again.' } as T; }
    if (res.status === 403) return res.json() as Promise<T>;
    if (!res.ok && res.status !== 409 && res.status !== 422) throw new Error(`${method} ${path} failed: ${res.status}`);
    return res.json() as Promise<T>;
  }

  checkAdministration(pid: string, mid: string) { return this.req<AdministrationCheck>('GET', `/api/patients/${pid}/medications/${mid}/administration-check`); }
  giveMedication(pid: string, mid: string, opts: GiveOptions = {}) { return this.req<Result>('POST', `/api/patients/${pid}/medications/${mid}/give`, opts); }
  holdMedication(pid: string, mid: string, reason: string) { return this.req<Result>('POST', `/api/patients/${pid}/medications/${mid}/hold`, { reason }); }
  holdForAlert(alertId: string) { return this.req<Result>('POST', `/api/alerts/${encodeURIComponent(alertId)}/hold`); }
  discontinueMedication(pid: string, mid: string) { return this.req<Result>('DELETE', `/api/patients/${pid}/medications/${mid}`); }

  getCatalog() { return this.req<CatalogDrug[]>('GET', '/api/catalog'); }
  checkMedication(pid: string, drugKey: string) { return this.req<CheckIssue[]>('POST', `/api/patients/${pid}/medication-check`, { drugKey }); }
  orderMedication(pid: string, drugKey: string, overrideReason?: string) { return this.req<Result>('POST', `/api/patients/${pid}/medications`, { drugKey, overrideReason }); }
  suggestAlternatives(pid: string, drugKey: string) { return this.req<Alternative[]>('POST', `/api/patients/${pid}/medication-alternatives`, { drugKey }); }

  acknowledgeAlert(alertId: string) { return this.req<Result>('POST', `/api/alerts/${encodeURIComponent(alertId)}/acknowledge`); }
  completeTask(pid: string, taskId: string) { return this.req<Result>('POST', `/api/patients/${pid}/tasks/${taskId}/complete`); }

  admitPatient(input: PatientInput) { return this.req<Result>('POST', '/api/patients', input); }
  updatePatient(pid: string, input: PatientInput) { return this.req<Result>('PUT', `/api/patients/${pid}`, input); }
  dischargePatient(pid: string) { return this.req<Result>('POST', `/api/patients/${pid}/discharge`); }
  async suggestBed(exceptPid?: string) { const r = await this.req<{ bed: string }>('GET', `/api/beds/suggest${exceptPid ? `?except=${exceptPid}` : ''}`); return r.bed; }

  getDrugInfo(name: string) { return this.req<DrugInfo | null>('GET', `/api/drug-info?name=${encodeURIComponent(name)}`); }

  async triggerScenario(key: string) { await this.req('POST', `/api/demo/scenarios/${key}`); }
  async resetDemo() { await this.req('POST', '/api/demo/reset'); }
  async skipMinutes(minutes: number) { await this.req('POST', '/api/demo/skip', { minutes }); }
  async setPaused(paused: boolean) { await this.req('POST', '/api/demo/pause', { paused }); }
}

import type {
  AdministrationCheck, AiText, Alternative, CatalogDrug, CheckIssue, Connection, DrugInfo, GiveOptions, LoginResult, PatientInput, Result, Snapshot, User,
} from '../types';
import { MockApi } from './mock';
import { HttpApi } from './http';

/**
 * Everything the UI needs from the backend. The UI only talks to this interface.
 *  - MockApi runs the whole Vital engine in the browser (demo mode, no server).
 *  - HttpApi talks to the FastAPI backend (REST + WebSocket). See README for the contract.
 */
export interface VitalApi {
  // live state
  start(): void;
  subscribe(listener: () => void): () => void;
  getSnapshot(): Snapshot | null;
  getConnection(): Connection;

  // session (production: hospital SSO + badge tap)
  getUsers(): Promise<User[]>;
  login(username: string, pin: string): Promise<LoginResult>;
  logout(): Promise<void>;
  getUser(): User | null;

  // medication administration
  checkAdministration(pid: string, mid: string): Promise<AdministrationCheck>;
  giveMedication(pid: string, mid: string, opts?: GiveOptions): Promise<Result>;
  holdMedication(pid: string, mid: string, reason: string): Promise<Result>;
  holdForAlert(alertId: string): Promise<Result>;
  discontinueMedication(pid: string, mid: string): Promise<Result>;

  // new orders
  getCatalog(): Promise<CatalogDrug[]>;
  checkMedication(pid: string, drugKey: string): Promise<CheckIssue[]>;
  orderMedication(pid: string, drugKey: string, overrideReason?: string): Promise<Result>;
  suggestAlternatives(pid: string, drugKey: string): Promise<Alternative[]>;

  // alerts and tasks
  acknowledgeAlert(alertId: string): Promise<Result>;
  completeTask(pid: string, taskId: string): Promise<Result>;

  // patients
  admitPatient(input: PatientInput): Promise<Result>;
  updatePatient(pid: string, input: PatientInput): Promise<Result>;
  dischargePatient(pid: string): Promise<Result>;
  suggestBed(exceptPid?: string): Promise<string>;

  // Vital AI (Person 3)
  getSbar(pid: string): Promise<AiText>;
  getHandoff(pid: string): Promise<AiText>;
  sendSbar(pid: string, text: string): Promise<Result>;

  // reference
  getDrugInfo(name: string): Promise<DrugInfo | null>;

  // demo-only controls (not in production)
  triggerScenario(key: string): Promise<void>;
  resetDemo(): Promise<void>;
  skipMinutes(minutes: number): Promise<void>;
  setPaused(paused: boolean): Promise<void>;
}

const baseUrl = (import.meta.env.VITE_API_URL as string | undefined)?.trim();

export const api: VitalApi = baseUrl ? new HttpApi(baseUrl) : new MockApi();
export const isDemoMode = !baseUrl;

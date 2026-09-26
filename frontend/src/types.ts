// Shared types between the UI and the API layer.
// Field names are kept close to the FHIR resources they will map to (see README).

export type Severity = 'crit' | 'warn' | 'info';

export interface Vitals { sbp: number; dbp: number; hr: number; rr: number; spo2: number }
export type VitalKey = keyof Vitals;

export interface LabValue { v: number; t: number; prev?: number }
export type LabKey = 'k' | 'cr' | 'glu' | 'inr' | 'hgb' | 'lac';
export type Labs = { k: LabValue; cr: LabValue; glu: LabValue } & Partial<Record<'inr' | 'hgb' | 'lac', LabValue>>;

/** FHIR: AllergyIntolerance */
export interface Allergy { agent: string; cls: string; rxn: string; intol?: boolean }

export interface TimeCritical { due: number; grace: number; why: string }

export type MedStatus = 'due' | 'given' | 'held';

/** FHIR: MedicationRequest (+ MedicationAdministration for status/at/cosign) */
export interface Medication {
  id: string;
  name: string;
  dose: string;
  route: string;
  freq: string;
  due: string;            // "09:00" or "PRN"
  cls: string[];          // drug classes used by the rules engine
  hold?: { sbp?: number; hr?: number };
  param?: string;         // human-readable hold parameter
  effect?: string;
  renal?: boolean;
  apap?: number;          // max acetaminophen mg/day this order allows
  beers?: boolean;
  qt?: boolean;
  dilt?: boolean;
  tc?: TimeCritical;      // time-critical window
  isNew?: boolean;
  orderedAt?: number;
  catKey?: string;        // ordered through the new-medication check
  status: MedStatus;
  at: number | null;
  cosign?: string;
}

/** FHIR: Task */
export interface CareTask { id: string; name: string; due: number; grace: number; why: string; done: boolean; at: number | null }

/** FHIR: Patient + Encounter + Condition + Observation */
export interface Patient {
  id: string;
  bed: string;
  name: string;
  age: number;
  sex: 'F' | 'M';
  wt: number;
  dx: string;
  conditions: string[];
  otherConds?: string[];
  allergies: Allergy[];
  vit: Vitals;
  target: Vitals;
  base: Vitals;
  hist: Record<VitalKey, number[]>;
  labs: Labs;
  meds: Medication[];
  tasks: CareTask[];
}

export interface Alert {
  id: string;
  pid: string;
  sev: Severity;
  meds: string[];
  trigger: string;
  title: string;
  why: string;
  data: string[];
  action: string;
  task?: string | null;
  timing?: boolean;
  firstSeen: number;
}

export interface CheckIssue { sev: Severity; type: string; title: string; why: string; action: string }

export interface LogEntry { t: number; text: string; kind: '' | 'crit' | 'warn' | 'ok' }

export interface ScenarioView { key: string; pid: string; label: string; patientLabel: string; used: boolean }

export interface DischargedPatient { name: string; bed: string; at: number }

export interface Snapshot {
  sim: number;                 // minutes since 08:40 (demo clock)
  paused: boolean;
  patients: Patient[];
  alerts: Alert[];             // active critical + warning alerts
  heldBack: Alert[];           // low-priority checks (not shown as interruptions)
  log: LogEntry[];
  discharged: DischargedPatient[];
  scenarios: ScenarioView[];
}

export interface CatalogDrug {
  key: string; name: string; dose: string; route: string; freq: string; due: string; cls: string[]; apap?: number;
  group: string;          // therapeutic group, used to suggest safer alternatives
  tall?: string;          // tall-man lettering for look-alike names (ISMP), e.g. "HydrALAZINE"
  lasa?: string;          // key of the look-alike / sound-alike drug
  purpose?: string;       // short plain-language purpose, shown in LASA warnings
}

export interface Alternative { drug: CatalogDrug; issues: CheckIssue[] }

export type Role = 'nurse' | 'charge' | 'pharmacist' | 'provider';
export interface User { username: string; name: string; role: Role; title: string }
export type Permission = 'administer' | 'order' | 'admit' | 'discharge' | 'editPatient' | 'acknowledge' | 'tasks';
export type Connection = 'connecting' | 'online' | 'offline';

export interface DrugInfo { cls: string; use: string; watch: string; nursing: string }

export interface ExpectedDose { n: number; unit: string; calc: string }

export interface AdministrationCheck {
  blocking: Alert[];           // alerts the nurse must see before giving
  highAlert: boolean;
  expected: ExpectedDose | null;
}

export interface GiveOptions { overrideReason?: string; cosigner?: string; cosignPin?: string; cosignDose?: number }

export interface Result { ok: boolean; error?: string; id?: string }
export interface LoginResult { ok: boolean; error?: string; user?: User }

export interface PatientInput {
  name: string;
  age: number;
  sex: 'F' | 'M';
  wt: number;
  bed: string;
  dx: string;
  conditions: string[];
  otherConds: string[];
  allergies: Allergy[];
}

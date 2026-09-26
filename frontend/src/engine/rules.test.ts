import { describe, expect, it } from 'vitest';
import { MockApi } from '../api/mock';
import { CATALOG } from './data';
import { checkNewMedication } from './checker';
import { evaluate } from './rules';
import { crcl } from './util';

const fresh = (user = 'jrivera') => { const api = new MockApi(); void api.login(user, '1234'); return { api, snap: () => api.getSnapshot()! }; };
const drug = (key: string) => CATALOG.find(d => d.key === key)!;

describe('Vital rules engine', () => {
  it('starts calm: no critical alerts on a fresh shift', () => {
    const { snap } = fresh();
    expect(snap().alerts.filter(a => a.sev === 'crit')).toHaveLength(0);
    expect(snap().heldBack.length).toBeGreaterThan(0);
  });

  it('flags high potassium on ACE inhibitor + spironolactone', async () => {
    const { api, snap } = fresh();
    await api.triggerScenario('k');
    const a = snap().alerts.find(x => x.id === 'k:p1');
    expect(a?.sev).toBe('crit');
    expect(a?.meds).toHaveLength(2);
  });

  it('undo restores the lab and clears the alert', async () => {
    const { api, snap } = fresh();
    await api.triggerScenario('k');
    await api.triggerScenario('k');
    expect(snap().alerts.find(x => x.id === 'k:p1')).toBeUndefined();
    expect(snap().patients[0].labs.k.v).toBe(4.6);
  });

  it('computes Cockcroft-Gault CrCl', () => {
    const { snap } = fresh();
    const james = snap().patients.find(p => p.id === 'p2')!;
    expect(crcl(james)).toBe(63);
  });

  it('flags metformin as contraindicated when CrCl drops below 30', async () => {
    const { api, snap } = fresh();
    await api.triggerScenario('cr');
    expect(snap().alerts.some(a => a.id === 'renal:p2:m1' && a.sev === 'crit')).toBe(true);
  });
});

describe('New-medication check', () => {
  it('blocks lisinopril in pregnancy', () => {
    const { snap } = fresh();
    const priya = snap().patients.find(p => p.id === 'p8')!;
    expect(checkNewMedication(priya, drug('lisi')).some(i => i.sev === 'crit' && i.type === 'Pregnancy')).toBe(true);
  });
  it('distinguishes propranolol (critical) from metoprolol (warning) in asthma', () => {
    const { snap } = fresh();
    const luis = snap().patients.find(p => p.id === 'p6')!;
    expect(checkNewMedication(luis, drug('prop'))[0].sev).toBe('crit');
    expect(checkNewMedication(luis, drug('meto')).every(i => i.sev !== 'crit')).toBe(true);
  });
  it('catches the penicillin allergy', () => {
    const { snap } = fresh();
    const james = snap().patients.find(p => p.id === 'p2')!;
    expect(checkNewMedication(james, drug('amox'))[0].type).toBe('Allergy');
  });
  it('requires a reason to order through a critical issue', async () => {
    const { api } = fresh('spatel');
    expect((await api.orderMedication('p9', 'reglan')).ok).toBe(false);
    expect((await api.orderMedication('p9', 'reglan', 'Will monitor closely')).ok).toBe(true);
  });
});

describe('Administration', () => {
  it('insulin needs a matching independent double-check', async () => {
    const { api, snap } = fresh();
    const chk = await api.checkAdministration('p2', 'm2');
    expect(chk.highAlert).toBe(true);
    expect(chk.expected?.n).toBe(2);
    expect((await api.giveMedication('p2', 'm2', { cosigner: 'mchen', cosignPin: '1234', cosignDose: 4 })).ok).toBe(false);
    expect((await api.giveMedication('p2', 'm2', { cosigner: 'mchen', cosignPin: '0000', cosignDose: 2 })).ok).toBe(false);
    expect((await api.giveMedication('p2', 'm2', { cosigner: 'jrivera', cosignPin: '1234', cosignDose: 2 })).ok).toBe(false);
    expect((await api.giveMedication('p2', 'm2', { cosigner: 'mchen', cosignPin: '1234', cosignDose: 2 })).ok).toBe(true);
    expect(snap().patients.find(p => p.id === 'p2')!.meds.find(m => m.id === 'm2')!.cosign).toBe('RN Maria Chen');
  });
  it('escalates a late sepsis antibiotic to critical', async () => {
    const { api, snap } = fresh();
    await api.skipMinutes(60);
    expect(snap().alerts.some(a => a.id === 'tc:p11:m1:crit')).toBe(true);
  });
});

describe('Patients', () => {
  it('admits, edits and discharges', async () => {
    const { api, snap } = fresh('sreyes');
    const r = await api.admitPatient({ name: 'Carmen Díaz', age: 68, sex: 'F', wt: 60, bed: '430B', dx: 'Hip fracture', conditions: ['CKD'], otherConds: [], allergies: [{ agent: 'Penicillin', cls: 'penicillin', rxn: 'hives' }] });
    expect(r.ok).toBe(true);
    const clash = await api.updatePatient(r.id!, { name: 'Carmen Díaz', age: 68, sex: 'F', wt: 60, bed: '412A', dx: '', conditions: [], otherConds: [], allergies: [] });
    expect(clash.ok).toBe(false);
    await api.dischargePatient(r.id!);
    expect(snap().patients.some(p => p.id === r.id)).toBe(false);
    expect(snap().discharged[0].name).toBe('Carmen Díaz');
  });
  it('re-checks orders when allergies change', async () => {
    const { api, snap } = fresh();
    const p = snap().patients.find(x => x.id === 'p4')!;
    expect(evaluate(p, 0).some(a => a.id.startsWith('allergy'))).toBe(false);
    await api.updatePatient('p4', { name: p.name, age: p.age, sex: p.sex, wt: p.wt, bed: p.bed, dx: p.dx, conditions: p.conditions, otherConds: [],
      allergies: [{ agent: 'Morphine / opioids', cls: 'opioid', rxn: 'anaphylaxis' }] });
    expect(snap().alerts.some(a => a.id === 'allergy:p4:m2' && a.sev === 'crit')).toBe(true);
  });
});

describe('Roles and alternatives', () => {
  it('blocks actions outside the role', async () => {
    const nurse = fresh('jrivera').api;
    expect((await nurse.orderMedication('p1', 'apap')).ok).toBe(false);
    expect((await nurse.dischargePatient('p1')).ok).toBe(false);
    const doc = fresh('spatel').api;
    expect((await doc.giveMedication('p6', 'm2')).ok).toBe(false);
    expect((await doc.orderMedication('p1', 'apap')).ok).toBe(true);
  });
  it('rejects a wrong PIN', async () => {
    const api = new MockApi();
    expect((await api.login('jrivera', '9999')).ok).toBe(false);
    expect(api.getUser()).toBeNull();
  });
  it('suggests safer alternatives that pass every check', async () => {
    const { api } = fresh();
    const alts = await api.suggestAlternatives('p1', 'ibu');
    expect(alts.length).toBeGreaterThan(0);
    expect(alts[0].drug.key).toBe('apap');
    expect(alts.every(a => a.issues.every(i => i.sev !== 'crit'))).toBe(true);
  });
});

// Exports the demo data as JSON so the Python backend, engine and AI can test against
// exactly what the frontend uses.  Run:  npm run fixtures
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { MockApi } from '../src/api/mock';
import { ALLERGENS, BED_POOL, CATALOG, CLS_LABEL, COND, DRUG_INFO, GROUP_LABEL, SEED_PATIENTS, USERS } from '../src/engine/data';
import { PERMISSIONS } from '../src/engine/permissions';
import { checkNewMedication } from '../src/engine/checker';
import { expectedDose } from '../src/engine/doubleCheck';
import { isHighAlert } from '../src/engine/util';

const out = resolve(__dirname, '../../backend/fixtures');
mkdirSync(out, { recursive: true });
const write = (name: string, data: unknown) => writeFileSync(resolve(out, name), JSON.stringify(data, null, 2) + '\n');

async function main() {
  const api = new MockApi();
  await api.login('jrivera', '1234');
  const calm = api.getSnapshot()!;

  // A few "after" snapshots so every rule has an example to test against.
  const scen = async (key: string) => { const a = new MockApi(); await a.login('jrivera', '1234'); await a.triggerScenario(key); return a.getSnapshot()!; };
  const late = new MockApi(); await late.login('jrivera', '1234'); await late.skipMinutes(60);

  write('patients.json', SEED_PATIENTS);
  write('snapshot.json', calm);
  write('snapshot-potassium-5.8.json', await scen('k'));
  write('snapshot-creatinine-2.8.json', await scen('cr'));
  write('snapshot-after-60-min.json', late.getSnapshot());
  write('catalog.json', CATALOG);
  write('drug-info.json', DRUG_INFO);
  write('reference.json', { conditions: COND, classLabels: CLS_LABEL, groupLabels: GROUP_LABEL, allergens: ALLERGENS, beds: BED_POOL, permissions: PERMISSIONS });
  write('users.demo.json', USERS);

  // Expected results of the new-medication check: every patient x every catalog drug.
  write('checker-cases.json', calm.patients.flatMap(p => CATALOG.map(d => ({
    patient: p.id, drug: d.key, issues: checkNewMedication(p, d).map(i => ({ sev: i.sev, type: i.type, title: i.title })),
  }))));
  // Expected double-check doses for every high-alert order.
  write('double-check-cases.json', calm.patients.flatMap(p => p.meds.filter(isHighAlert).map(m => ({ patient: p.id, med: m.id, expected: expectedDose(p, m) }))));
  console.log('Fixtures written to', out);
}
main();

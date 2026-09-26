// "Check a new medication": runs every safety rule on a drug BEFORE it is ordered.
// Port this file to the Python backend (it is the same logic the server should own).
import type { CatalogDrug, CheckIssue, Patient, Severity } from '../types';
import { CLS_LABEL } from './data';
import { crcl, firstName, listNames, roundVitals, sevRank } from './util';

export function checkNewMedication(p: Patient, d: CatalogDrug, selfId?: string): CheckIssue[] {
  const I: CheckIssue[] = [], others = p.meds.filter(m => m.id !== selfId);
  const has = (c: string) => others.filter(m => m.cls.includes(c)), cond = (c: string) => p.conditions.includes(c), dc = (c: string) => d.cls.includes(c);
  const c = crcl(p), L = p.labs, v = roundVitals(p.vit), first = firstName(p);
  const add = (sev: Severity, type: string, title: string, why: string, action: string) => { I.push({ sev, type, title, why, action }); };

  p.allergies.forEach(a => { if (!dc(a.cls)) return;
    if (a.intol) add('warn','Intolerance',`Documented ${a.agent.toLowerCase()} intolerance`,`${first} had ${a.rxn.replace(' (intolerance)','')} with ${a.agent.toLowerCase()}. This is an intolerance, not a true allergy.`,'Consider a different pain medication, or pre-treat for nausea.');
    else add('crit','Allergy',`Allergy: ${d.name} is a ${CLS_LABEL[a.cls]||a.cls}`,`${first} has a documented ${a.agent.toLowerCase()} allergy (${a.rxn}).`,'Do not order. Choose a drug from a different family.');
  });
  ['BB','CCB-nd','ACEi','NSAID','opioid','anticoag','statin','benzo','steroid','metformin','tetracycline'].forEach(cl => {
    if (!dc(cl)) return; const ex = has(cl); if (!ex.length) return;
    const soft = cl==='opioid' || cl==='anticoag';
    add(soft?'warn':'crit','Duplicate therapy',`Duplicate ${CLS_LABEL[cl]}: already on ${listNames(ex)}`,
      soft ? `${first} already has ${listNames(ex)} ordered. Two ${CLS_LABEL[cl]}s together ${cl==='opioid'?'add up sedation and can slow breathing':'raise bleeding risk'}, unless this is intentional${cl==='anticoag'?' (for example, bridging)':''}.`
           : `${first} is already on ${listNames(ex)}, from the same drug class. Giving both doubles the effect.`,
      soft ? 'Confirm with the provider that both are intended.' : 'Do not add. Adjust the existing order instead.');
  });
  if (d.apap) { const ap = others.filter(m => m.apap), tot = ap.reduce((s,m)=>s+(m.apap||0),0) + (d.apap||0);
    if (ap.length && tot > 4000) add('crit','Duplicate ingredient','Acetaminophen over the daily max',`${listNames(ap)} already ${ap.length>1?'contain':'contains'} acetaminophen. Adding this allows up to ${tot.toLocaleString()} mg a day. The max is 4,000 mg.`,'Do not add. Use the existing acetaminophen order.'); }
  if (dc('NSAID')) {
    if (has('warfarin').length) add('crit','Drug interaction','Bleeding risk with warfarin',`NSAIDs plus warfarin raise the risk of serious bleeding.${L.inr?` INR is ${L.inr.v}.`:''}`,'Avoid. Consider acetaminophen for pain.');
    if (cond('HF')) { const tw = has('ACEi').length && has('loop').length;
      add(tw?'crit':'warn','Condition', tw?'Heart failure + ACE inhibitor + diuretic ("triple whammy")':'Can worsen heart failure',
        tw ? `${first} has heart failure and takes ${listNames([...has('ACEi'),...has('loop')])}. Adding an NSAID to an ACE inhibitor and a diuretic is a known cause of acute kidney injury, and NSAIDs cause fluid retention.` : 'NSAIDs cause salt and fluid retention and can trigger a heart failure flare.',
        'Avoid NSAIDs. Consider acetaminophen.'); }
    if (cond('CKD') || c < 60) add(c<30?'crit':'warn','Kidney function',`Kidney function: CrCl ${c} mL/min`,`NSAIDs reduce blood flow to the kidneys${cond('CKD')?', and '+first+' has chronic kidney disease':''}.`,'Avoid, or use the lowest dose for the shortest time.');
    if (cond('ASTHMA')) add('warn','Condition','Asthma: NSAIDs can trigger bronchospasm','Some people with asthma react to NSAIDs.','Ask whether the patient has taken NSAIDs safely before.');
    if (p.age >= 65) add('warn','Age',`Age ${p.age}: stomach bleeding risk (Beers list)`,'NSAIDs raise the risk of stomach bleeding in older adults.','Use the lowest dose for the shortest time, or choose acetaminophen.');
  }
  if (dc('BB')) {
    if (cond('ASTHMA')) add(dc('BB-ns')?'crit':'warn','Condition', dc('BB-ns')?'Contraindicated in asthma':'Use caution in asthma',
      dc('BB-ns') ? `${d.name} also blocks beta receptors in the lungs and can cause severe bronchospasm.` : `${d.name} is cardioselective, but it can still tighten airways at higher doses.`,
      dc('BB-ns') ? 'Do not order. If a beta-blocker is needed, ask about a cardioselective one.' : 'Use the lowest dose and monitor breathing.');
    const nd = has('CCB-nd'); if (nd.length) add('warn','Drug interaction',`Slow heart rate with ${listNames(nd)}`,`Beta-blockers and ${listNames(nd)} both slow the heart. Together they can cause bradycardia or heart block.`,'Check heart rate and ECG, and confirm with the provider.');
    if (v.hr < 60) add('warn','Vitals',`Heart rate is ${v.hr}`,'A beta-blocker would slow it further.','Recheck heart rate before the first dose.');
  }
  if (dc('CCB-nd')) {
    const bb = has('BB'); if (bb.length) add('crit','Drug interaction',`Heart block risk with ${listNames(bb)}`,`${d.name} plus ${listNames(bb)} can dangerously slow heart rate and conduction.`,'Avoid this combination.');
    if (cond('HF')) add('crit','Condition','Can worsen heart failure',`${d.name} weakens heart contraction and is avoided in heart failure with reduced ejection fraction.`,'Choose a different drug.');
  }
  if (dc('tmpsmx')) {
    if (has('warfarin').length) add('crit','Drug interaction','Raises INR with warfarin','This antibiotic blocks warfarin breakdown. INR can rise quickly and cause bleeding.','Choose a different antibiotic, or lower warfarin and check INR closely.');
    const kk = [...has('ACEi'),...has('ARB'),...has('Ksparing')];
    if (kk.length) add(has('Ksparing').length?'crit':'warn','Drug interaction','High potassium risk',`Trimethoprim raises potassium, and so ${kk.length>1?'do':'does'} ${listNames(kk)}. Current K+ is ${L.k.v} mmol/L.`,'Choose a different antibiotic, or monitor potassium closely.');
    if (c < 30) add('warn','Kidney function',`Dose adjustment: CrCl ${c} mL/min`,'This antibiotic is cleared by the kidneys.','Reduce the dose by half.');
  }
  if (dc('azole')) {
    if (has('warfarin').length) add('crit','Drug interaction','Raises INR with warfarin','Fluconazole strongly blocks warfarin breakdown. INR can double within days.','Lower the warfarin dose and recheck INR in 3 days, or choose another antifungal.');
    if (has('statin').length) add('warn','Drug interaction',`Raises ${listNames(has('statin'))} levels`,'Higher statin levels raise the risk of muscle damage.','Watch for muscle pain; consider holding the statin.');
  }
  if (dc('macrolide-strong')) {
    if (has('statin').length) add('warn','Drug interaction',`Raises ${listNames(has('statin'))} levels`,'Clarithromycin sharply raises statin levels, with a risk of muscle breakdown (rhabdomyolysis).','Hold the statin during the antibiotic course.');
    if (has('warfarin').length) add('warn','Drug interaction','Can raise INR with warfarin','Clarithromycin slows warfarin breakdown.','Check INR within a few days.');
    if (has('CCB-nd').length) add('warn','Drug interaction',`Raises ${listNames(has('CCB-nd'))} levels`,'Can cause low blood pressure and slow heart rate.','Monitor BP and heart rate.');
  }
  if (dc('QT')) { const q = has('QT'); if (q.length) add('warn','Drug interaction','QT prolongation risk',`${d.name} and ${listNames(q)} both prolong the QT interval, which can trigger a dangerous heart rhythm.`,'Get a baseline ECG and check potassium and magnesium.'); }
  if (dc('quinolone')) {
    if (has('warfarin').length) add('warn','Drug interaction','Can raise INR with warfarin','Ciprofloxacin can increase warfarin effect.','Check INR within a few days.');
    if (p.age >= 65) add('warn','Age',`Age ${p.age}: tendon and confusion risk`,'Fluoroquinolones carry an FDA boxed warning for tendon rupture, and older adults are at higher risk.','Consider another antibiotic if one fits.');
  }
  if (dc('benzo') || dc('sedative') || dc('sedating')) {
    const op = has('opioid'); if (op.length) add(dc('benzo')?'crit':'warn','Drug interaction','Breathing risk with opioids',`${d.name} plus ${listNames(op)} can cause deep sedation and slowed breathing.${dc('benzo')?' The FDA has a boxed warning for this combination.':''}`,'Avoid, or use the lowest doses with continuous SpO2 monitoring.');
    if (p.age >= 65) add('warn','Age',`Age ${p.age}: falls and confusion (Beers list)`,`${d.name} raises the risk of falls, delirium and fractures in older adults.`,'Try non-drug sleep or anxiety measures first.');
    if (v.spo2 < 92) add('warn','Vitals',`SpO2 is ${v.spo2}%`,'A sedative could lower it further.','Assess breathing before giving.');
  }
  if (dc('opioid')) { const bz = has('benzo'); if (bz.length) add('crit','Drug interaction',`Breathing risk with ${listNames(bz)}`,'Opioids plus benzodiazepines can stop breathing. The FDA has a boxed warning for this combination.','Avoid, or use the lowest doses with continuous SpO2 monitoring.'); }
  if (dc('Ksupp')) {
    const kk = [...has('ACEi'),...has('ARB'),...has('Ksparing')];
    if (L.k.v > 5.0) add('crit','Lab',`Potassium is already ${L.k.v}`,'Adding potassium could push it to a dangerous level.','Do not order.');
    else if (kk.length) add(kk.length>=2?'crit':'warn','Drug interaction','High potassium risk',`${listNames(kk)} already ${kk.length>1?'raise':'raises'} potassium. Current K+ is ${L.k.v} mmol/L.`,'Confirm the need with a repeat potassium first.');
  }
  if (dc('TZD')) {
    if (cond('HF')) add('crit','Condition','Contraindicated in heart failure','Pioglitazone causes fluid retention and has an FDA boxed warning for heart failure.','Choose a different diabetes medication.');
    if (has('insulin').length) add('warn','Drug interaction','Fluid retention with insulin','Pioglitazone with insulin raises the risk of swelling and fluid overload.','Monitor weight and swelling.');
  }
  if (dc('SU')) {
    if (has('insulin').length) add('warn','Drug interaction','Low blood sugar risk with insulin',`Glipizide and ${listNames(has('insulin'))} both lower blood sugar.`,'Confirm the combination and increase fingerstick checks.');
    if (c < 50) add('warn','Kidney function',`Kidney function: CrCl ${c} mL/min`,'Lower kidney function raises the risk of low blood sugar.','Start at the lowest dose.');
    if (L.glu.v < 100) add('warn','Lab',`Glucose is ${L.glu.v} mg/dL`,'Blood sugar is already on the low side.','Recheck glucose before ordering.');
  }
  if (dc('metformin')) {
    if (c < 30) add('crit','Kidney function',`Contraindicated: CrCl ${c} mL/min`,'Metformin can build up and cause lactic acidosis when kidney function is below 30.','Choose a different diabetes medication.');
    else if (c < 45) add('warn','Kidney function',`Dose limit: CrCl ${c} mL/min`,'Metformin needs a lower maximum dose at this kidney function.','Keep the total dose at or below 1,000 mg a day.');
  }
  if (dc('nitroimidazole') && has('warfarin').length) add('crit','Drug interaction','Raises INR with warfarin','Metronidazole strongly blocks warfarin breakdown. INR can rise sharply and cause bleeding.','Choose a different antibiotic, or lower warfarin and check INR in 3 days.');
  if (dc('vasodilator') && v.sbp < 110) add('warn','Vitals',`Blood pressure is ${v.sbp}/${v.dbp}`,`${d.name} is for severe high blood pressure. The current reading is not high.`,'Confirm the indication before ordering.');
  if (dc('antiplatelet') && has('anticoag').length) add('warn','Drug interaction',`Bleeding risk with ${listNames(has('anticoag'))}`,'Aspirin plus an anticoagulant raises bleeding risk.','Confirm there is a clear reason for both.');
  if (dc('LMWH') && c < 30) add('warn','Kidney function',`Dose adjustment: CrCl ${c} mL/min`,'Enoxaparin builds up when kidney function is below 30.','Use 30 mg daily for prevention.');
  if (cond('PREG')) {
    if (dc('ACEi')) add('crit','Pregnancy','Contraindicated in pregnancy',"ACE inhibitors can damage the baby's kidneys and cause low amniotic fluid, especially in the 2nd and 3rd trimesters.",'Do not order. Labetalol or nifedipine are preferred in pregnancy.');
    if (dc('NSAID')) add('crit','Pregnancy','Avoid after 20 weeks of pregnancy','NSAIDs can lower amniotic fluid and, in the 3rd trimester, can close a vital fetal blood vessel (the ductus arteriosus) too early.','Use acetaminophen instead.');
    if (dc('tetracycline')) add('crit','Pregnancy','Avoid in pregnancy',"Tetracyclines can stain the baby's teeth and affect bone growth.",'Choose a different antibiotic.');
    if (dc('anticoag') && d.key!=='enox') add('crit','Pregnancy','Avoid in pregnancy','This anticoagulant can cause birth defects.','Enoxaparin is the usual choice in pregnancy.');
    if (dc('quinolone')) add('warn','Pregnancy','Generally avoided in pregnancy','Safer antibiotic options are usually available.','Confirm with the provider.');
    if (dc('azole')) add('warn','Pregnancy','Fluconazole in pregnancy','Higher or repeated doses have been linked to birth defects.','Consider a topical antifungal.');
    if (dc('tmpsmx')) add('warn','Pregnancy','Late pregnancy','Sulfonamides close to delivery can raise the newborn’s bilirubin.','Choose a different antibiotic if possible.');
    if (dc('statin')) add('warn','Pregnancy','Usually stopped in pregnancy','Cholesterol drugs are generally paused during pregnancy.','Confirm with the provider.');
  }
  if (cond('PD') && dc('dopamine-block')) add('crit','Condition',"Worsens Parkinson's disease",`${d.name} blocks dopamine, the chemical that Parkinson's medication replaces. It can cause severe stiffness, freezing and swallowing problems.`,'Do not order. For nausea, ondansetron is a safer choice.');
  if (cond('GIB')) {
    if (dc('NSAID') || dc('antiplatelet')) add('crit','Condition','Active GI bleed',`${d.name} irritates the stomach lining and slows clotting. It can make the bleeding worse.`,'Do not order.');
    if (dc('anticoag')) add('crit','Condition','Active GI bleed','Anticoagulants are contraindicated while the patient is actively bleeding.','Do not order. For clot prevention, use compression devices.');
    if (dc('steroid')) add('warn','Condition','Raises ulcer bleeding risk','Steroids slow ulcer healing and raise bleeding risk.','Confirm the need with the provider.');
  }
  if (cond('DYSPH') && dc('ER') && d.route==='PO') add('warn','Condition','Dysphagia: extended-release tablet',`${first} has trouble swallowing and gets meds crushed. Crushing ${d.name} releases the whole dose at once.`,'Ask pharmacy for an immediate-release or liquid form.');
  if (dc('steroid') && cond('DM')) add('warn','Condition','Raises blood sugar in diabetes','Steroids raise glucose, often for several days.','Increase fingerstick checks; insulin may need adjusting.');
  return I.sort((a,b) => sevRank(a.sev) - sevRank(b.sev));
}

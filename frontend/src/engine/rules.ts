// The Vital rules engine: re-checks every active order for one patient.
// Called whenever a vital, lab, order or patient detail changes.
// Port this file to the Python backend (the server should own these rules).
import type { Alert, Patient } from '../types';
import { CATALOG } from './data';
import { checkNewMedication } from './checker';
import { crcl, firstName, fmt, hash, isActive, listNames, roundVitals } from './util';

export type NewAlert = Omit<Alert, 'firstSeen'>;

export function evaluate(p: Patient, sim: number): NewAlert[] {
  const A: NewAlert[] = [], v = roundVitals(p.vit), L = p.labs, meds = p.meds, now = fmt(sim), first = firstName(p);
  const add = (o: Omit<NewAlert, 'pid'>) => { A.push({ pid: p.id, ...o }); };
  const cls = (c: string) => meds.filter(m => m.cls.includes(c));

  // Hold parameters from the order
  meds.forEach(m => {
    if (!m.hold) return;
    const r = [];
    if (m.hold.sbp && v.sbp < m.hold.sbp) r.push(`systolic BP is ${v.sbp} (below ${m.hold.sbp})`);
    if (m.hold.hr && v.hr < m.hold.hr) r.push(`heart rate is ${v.hr} (below ${m.hold.hr})`);
    if (r.length) add({id:`hold:${p.id}:${m.id}`, sev:'crit', meds:[m.id], trigger:'Vital sign change',
      title:`Hold ${m.name}: below ordered parameter`,
      why:`${first}'s ${r.join(' and ')}. The order says "${m.param}." ${m.name} lowers ${m.effect} and would push them lower.`,
      data:[`BP ${v.sbp}/${v.dbp} mmHg · HR ${v.hr} · bedside monitor · ${now}`, `Order: ${m.name} ${m.dose} ${m.route} ${m.freq} · ${m.param}`],
      action:'Hold this dose. Recheck vitals in 15 minutes and notify the provider.'});
  });

  // BP trend (before it crosses the threshold)
  const win = p.hist.sbp.slice(-14), mx = Math.max(...win), drop = mx - v.sbp;
  if (drop >= 22 && v.sbp >= 90) {
    const due = meds.filter(m => isActive(m) && m.due !== 'PRN' && m.cls.some(c => ['ACEi','BB','CCB','loop'].includes(c)));
    if (due.length) add({id:`trend:${p.id}`, sev:'warn', meds:due.map(m=>m.id), trigger:'Vital sign trend',
      title:'Blood pressure falling fast',
      why:`Systolic BP dropped from ${mx} to ${v.sbp} in the last few minutes. It is still above 90, but ${listNames(due)} ${due.length>1?'are':'is'} due at ${due[0].due}.`,
      data:[`SBP ${mx} → ${v.sbp} mmHg · last 7 min · bedside monitor`],
      action:'Recheck BP right before giving any blood-pressure medication.'});
  }

  // Potassium
  const kMeds = meds.filter(m => m.cls.some(c => ['ACEi','ARB','Ksparing'].includes(c)));
  const k = L.k.v;
  if (kMeds.length) {
    const data = [`K+ ${k} mmol/L · lab result · ${fmt(L.k.t)}` + (L.k.prev!=null ? ` (was ${L.k.prev})` : ''), `Normal range 3.5–5.0 mmol/L`];
    if (k > 5.5) add({id:`k:${p.id}`, sev:'crit', meds:kMeds.map(m=>m.id), trigger:'New lab result',
      title:`High potassium: hold ${listNames(kMeds)}`,
      why:`Potassium is ${k} mmol/L. ${listNames(kMeds)} both raise potassium. At this level the risk of dangerous heart rhythms goes up.`,
      data, action:'Hold both. Repeat the potassium, get an ECG, and notify the provider.'});
    else if (k > 5.0) add({id:`k5:${p.id}`, sev:'warn', meds:kMeds.map(m=>m.id), trigger:'New lab result',
      title:'Potassium above normal', why:`Potassium is ${k} mmol/L and ${listNames(kMeds)} can raise it further.`, data,
      action:'Review with the provider before giving.'});
    else if (kMeds.length >= 2) add({id:`kinfo:${p.id}`, sev:'info', meds:[], trigger:'Order check',
      title:`${listNames(kMeds)}: potassium can rise`, why:`Known combination. Potassium is ${k}, within range. Daily labs are ordered.`, data:[], action:'No action needed now.'});
  }

  // Kidney function
  const c = crcl(p), cr = L.cr;
  const aki = cr.prev!=null && cr.v - cr.prev >= 0.3;
  const crData = [`Creatinine ${cr.v} mg/dL · lab result · ${fmt(cr.t)}` + (cr.prev!=null ? ` (was ${cr.prev})` : ''),
                  `Est. CrCl ${c} mL/min (Cockcroft-Gault, ${p.wt} kg, age ${p.age})`].concat(aki ? [`Rise of ${(cr.v-(cr.prev??cr.v)).toFixed(1)} mg/dL meets the acute kidney injury flag (≥ 0.3)`] : []);
  meds.forEach(m => {
    if (!m.renal) return;
    if (m.cls.includes('metformin') && c < 30) add({id:`renal:${p.id}:${m.id}`, sev:'crit', meds:[m.id], trigger:'New lab result',
      title:'Metformin contraindicated at current kidney function',
      why:`Creatinine went up and estimated CrCl is now ${c} mL/min. Metformin should not be used below 30. It can build up and cause lactic acidosis.`,
      data:crData, action:'Hold metformin and ask the provider to change diabetes therapy.'});
    else if (m.cls.includes('metformin') && c < 45) add({id:`renal45:${p.id}:${m.id}`, sev:'warn', meds:[m.id], trigger:'New lab result',
      title:'Metformin: review dose for kidney function', why:`Estimated CrCl is ${c} mL/min.`, data:crData, action:'Ask the provider whether to reduce the dose.'});
    if (m.cls.includes('LMWH') && c < 30) add({id:`renal:${p.id}:${m.id}`, sev:'warn', meds:[m.id], trigger:'New lab result',
      title:'Enoxaparin dose needs kidney adjustment',
      why:`Estimated CrCl is ${c} mL/min. For prevention doses below 30 mL/min, the usual dose is 30 mg daily, not 40 mg. Higher levels raise bleeding risk.`,
      data:crData, action:'Ask the provider or pharmacist to adjust the dose before giving.'});
  });

  // Glucose
  const g = L.glu.v, ins = meds.filter(m => m.cls.includes('insulin'));
  if (ins.length && g < 70) add({id:`glu:${p.id}`, sev:'crit', meds:ins.map(m=>m.id), trigger:'New point-of-care result',
    title:'Low blood sugar: hold insulin',
    why:`Fingerstick glucose is ${g} mg/dL. ${listNames(ins)} is due at ${ins[0].due} and would lower it further.`,
    data:[`Glucose ${g} mg/dL · fingerstick · ${fmt(L.glu.t)}`, `Hypoglycemia threshold < 70 mg/dL`],
    action:'Hold insulin. Follow the hypoglycemia protocol (15 g fast-acting carbs, recheck in 15 min) and notify the provider.'});

  // Warfarin / INR
  const war = cls('warfarin');
  if (war.length && L.inr) {
    const i = L.inr.v, d = [`INR ${i} · lab result · ${fmt(L.inr.t)}` + (L.inr.prev!=null ? ` (was ${L.inr.prev})` : ''), 'Target 2.0–3.0 for atrial fibrillation'];
    if (i > 4) add({id:`inr:${p.id}`, sev:'crit', meds:war.map(m=>m.id), trigger:'New lab result',
      title:'INR too high: hold warfarin', why:`INR is ${i}, well above the 2.0–3.0 target. Bleeding risk is high.`, data:d,
      action:"Hold tonight's warfarin, check for signs of bleeding, and notify the provider."});
    else if (i > 3) add({id:`inr3:${p.id}`, sev:'warn', meds:war.map(m=>m.id), trigger:'New lab result',
      title:'INR above target', why:`INR is ${i}.`, data:d, action:'Review the warfarin dose with the provider.'});
    const ns = cls('NSAID').filter(m => !m.catKey);
    if (ns.length) add({id:`nsaid:${p.id}`, sev: i > 4 ? 'crit' : 'warn', meds:ns.map(m=>m.id), trigger:'New order',
      title:`Bleeding risk: ${listNames(ns)} with warfarin`,
      why:`${listNames(ns)} together with warfarin raises the risk of bleeding, especially stomach bleeding. INR is ${i}.`,
      data:[`New order: ${ns.map(m=>`${m.name} ${m.dose} ${m.route} ${m.freq}`).join(', ')}`, `Active: Warfarin ${war[0].dose} daily`],
      action:'Hold ibuprofen and ask the provider about acetaminophen instead.'});
  }

  // Allergies
  meds.forEach(m => p.allergies.forEach(a => {
    if (!m.catKey && !a.intol && m.cls.includes(a.cls)) add({id:`allergy:${p.id}:${m.id}`, sev:'crit', meds:[m.id], trigger:'New order',
      title:`Allergy: ${m.name} is a ${a.cls}`,
      why:`${first} has a documented ${a.agent.toLowerCase()} allergy (${a.rxn}). ${m.name} belongs to the same drug family.`,
      data:[`Allergy list: ${a.agent} · ${a.rxn} · EHR`, `New order: ${m.name} ${m.dose} ${m.route} ${m.freq}`],
      action:'Do not give. Ask the provider for a non-penicillin alternative.'});
  }));

  // Duplicate ingredient: acetaminophen
  const ap = meds.filter(m => m.apap && !m.catKey), tot = ap.reduce((s,m)=>s+(m.apap||0), 0);
  if (ap.length > 1 && tot > 4000) {
    const flagged = ap.filter(m => m.isNew);
    add({id:`apap:${p.id}`, sev:'crit', meds:(flagged.length?flagged:ap).map(m=>m.id), trigger:'New order',
      title:'Duplicate acetaminophen: over the daily max',
      why:`Two orders contain acetaminophen: ${ap.map(m=>`${m.name} (up to ${(m.apap||0).toLocaleString()} mg/day)`).join(' and ')}. Together that is up to ${tot.toLocaleString()} mg a day. The max is 4,000 mg. Too much can cause liver injury.`,
      data:ap.map(m=>`${m.name} ${m.dose} ${m.route} ${m.freq}`),
      action:'Ask the provider to change the new order or stop the scheduled acetaminophen.'});
  }

  // Orders placed through the new-medication checker keep being re-checked
  meds.filter(m => m.catKey && isActive(m)).forEach(m => {
    const d = CATALOG.find(x => x.key === m.catKey);
    checkNewMedication(p, d!, m.id).forEach(i => add({id:`new:${p.id}:${m.id}:${hash(i.title)}`, sev:i.sev, meds:[m.id], trigger:'New order',
      title:`${m.name}: ${i.title}`, why:i.why, data:[`${i.type} check · ordered ${fmt(m.orderedAt ?? sim)}`], action:i.action}));
  });

  // Opioids + breathing
  const op = cls('opioid');
  if (op.length && (v.rr < 12 || v.spo2 < 90)) add({id:`resp:${p.id}`, sev:'crit', meds:op.map(m=>m.id), trigger:'Vital sign change',
    title:'Breathing is slowing: hold opioids',
    why:`Respiratory rate is ${v.rr}/min and SpO2 is ${v.spo2}%. ${listNames(op)} can slow breathing further.`,
    data:[`RR ${v.rr}/min · SpO2 ${v.spo2}% · bedside monitor · ${now}`, `Opioid orders: ${op.map(m=>m.name).join(', ')}`],
    action:'Hold opioids. Check sedation, stimulate the patient, apply oxygen, follow the naloxone protocol if needed, and notify the provider.'});

  // Hemoglobin / lactate
  if (L.hgb && L.hgb.v < 7) add({id:`hgb:${p.id}`, sev:'crit', meds:[], trigger:'New lab result', title:'Hemoglobin below transfusion threshold',
    why:`Hemoglobin is ${L.hgb.v} g/dL${L.hgb.prev!=null?` (was ${L.hgb.prev})`:''}. With an active GI bleed, transfusion is usually considered below 7.`,
    data:[`Hgb ${L.hgb.v} g/dL · lab result · ${fmt(L.hgb.t)}`, `HR ${v.hr} · BP ${v.sbp}/${v.dbp}`], action:'Notify the provider now, confirm type and crossmatch, and check for signs of ongoing bleeding.'});
  if (L.lac && L.lac.v >= 4) add({id:`lac:${p.id}`, sev:'crit', meds:[], trigger:'New lab result', title:'Lactate 4 or higher: septic shock risk',
    why:`Lactate is ${L.lac.v} mmol/L.`, data:[`Lactate ${L.lac.v} mmol/L · ${fmt(L.lac.t)}`], action:'Start the 30 mL/kg fluid bolus and notify the provider.'});

  // Time-critical meds and timed care tasks
  const tcItems = meds.filter(m => m.tc && isActive(m)).map(m => ({kind:'med', id:m.id, name:m.name, due:m.tc!.due, grace:m.tc!.grace, why:m.tc!.why}))
    .concat((p.tasks||[]).filter(t => !t.done).map(t => ({kind:'task', id:t.id, name:t.name, due:t.due, grace:t.grace, why:t.why})));
  tcItems.forEach(x => {
    const left = x.due - sim, base = {meds: x.kind==='med' ? [x.id] : [], task: x.kind==='task' ? x.id : null, timing:true, trigger:'Time-critical'};
    if (left <= -x.grace) add(Object.assign({id:`tc:${p.id}:${x.id}:crit`, sev:'crit' as const, title:`Late: ${x.name}`,
      why:`${x.name} was due at ${fmt(x.due)} and is now ${Math.max(1,Math.floor(-left))} min late. ${x.why}`,
      data:[`Due ${fmt(x.due)}${x.grace?` · ${x.grace}-min window`:''} · now ${fmt(sim)}`],
      action: x.kind==='med' ? 'Give it now, or notify the provider if it cannot be given.' : 'Complete it now and document, or notify the provider.'}, base));
    else if (left <= 15) add(Object.assign({id:`tc:${p.id}:${x.id}:warn`, sev:'warn' as const, title: left > 0 ? `Due soon: ${x.name}` : `Overdue: ${x.name}`,
      why: left > 0 ? `Due at ${fmt(x.due)}, in ${Math.ceil(left)} min. ${x.why}` : `Was due at ${fmt(x.due)}. Becomes critical at ${fmt(x.due + x.grace)}. ${x.why}`,
      data:[`Due ${fmt(x.due)} · now ${fmt(sim)}`], action: x.kind==='med' ? 'Give on time.' : 'Complete on time.'}, base));
  });

  // Low-priority checks (held back)
  if (cls('ACEi').length && cls('loop').length) add({id:`i1:${p.id}`, sev:'info', meds:[], trigger:'Order check', title:'Lisinopril + furosemide: additive BP lowering', why:'Common, intended combination. Vitals are monitored.', data:[], action:''});
  meds.filter(m=>m.beers && p.age>=65).forEach(m => add({id:`beers:${p.id}:${m.id}`, sev:'info', meds:[], trigger:'Order check', title:`${m.name} in a patient over 65 (Beers list)`, why:'May cause confusion or falls. Already a PRN with fall precautions.', data:[], action:''}));
  if (cls('steroid').length) add({id:`st:${p.id}`, sev:'info', meds:[], trigger:'Order check', title:'Prednisone can raise glucose', why:`Glucose is ${g} mg/dL. Fingerstick checks are ordered.`, data:[], action:''});
  if (meds.some(m=>m.dilt) && cls('CCB').length) add({id:`dil:${p.id}`, sev:'info', meds:[], trigger:'Order check', title:'Diltiazem can raise atorvastatin levels', why:'Dose is within the usual limit. Monitor for muscle pain.', data:[], action:''});
  if (meds.some(m=>m.qt)) add({id:`qt:${p.id}`, sev:'info', meds:[], trigger:'Order check', title:'Ondansetron: low QT risk at this dose', why:'No other QT-prolonging drugs active.', data:[], action:''});
  if (cls('tetracycline').length && p.sex==='F' && !p.conditions.includes('PREG')) add({id:`dx:${p.id}`, sev:'info', meds:[], trigger:'Order check', title:'Doxycycline: pregnancy test negative on admission', why:'Take upright with a full glass of water.', data:[], action:''});
  if (p.conditions.includes('PREG') && cls('BB').length) add({id:`pr:${p.id}`, sev:'info', meds:[], trigger:'Order check', title:'Labetalol + nifedipine: preferred in pregnancy', why:'Both are first-line for high blood pressure in pregnancy.', data:[], action:''});
  if (p.conditions.includes('DYSPH')) add({id:`dy:${p.id}`, sev:'info', meds:[], trigger:'Order check', title:'Dysphagia: oral meds crushed per swallow evaluation', why:'Check each new oral order can be crushed.', data:[], action:''});
  if (p.conditions.includes('GIB')) add({id:`gi:${p.id}`, sev:'info', meds:[], trigger:'Order check', title:'NPO: all medications given IV', why:'NSAIDs, aspirin and anticoagulants will be blocked for this patient.', data:[], action:''});
  if (cls('glycopeptide').length) add({id:`va:${p.id}`, sev:'info', meds:[], trigger:'Order check', title:'Vancomycin: infuse over at least 90 minutes', why:`Est. CrCl ${c} mL/min. Pharmacy will dose follow-up by levels.`, data:[], action:''});
  if (cls('macrolide').length) add({id:`az:${p.id}`, sev:'info', meds:[], trigger:'Order check', title:'Azithromycin: QT prolongation (rare)', why:'No other risk factors found.', data:[], action:''});
  if (cls('LMWH').length && c >= 30) add({id:`lm:${p.id}`, sev:'info', meds:[], trigger:'Order check', title:'Enoxaparin: kidney function OK for current dose', why:`Est. CrCl ${c} mL/min.`, data:[], action:''});
  if (cls('cephalosporin').length && p.allergies.some(a=>a.cls==='penicillin')) add({id:`ceph:${p.id}`, sev:'info', meds:[], trigger:'Order check', title:'Cefazolin with penicillin allergy', why:'Low cross-reactivity; tolerated previous doses without reaction.', data:[], action:''});
  return A;
}


// Reference data for the demo. In production this comes from the hospital's
// drug database (First Databank / Medi-Span / Lexicomp) and the EHR.
import type { Allergy, CareTask, CatalogDrug, DrugInfo, Labs, Medication, User, Vitals } from '../types';

export const COND: Record<string, string> = {PREG:'Pregnant', PID:'Pelvic inflammatory disease', PD:"Parkinson's disease", DYSPH:'Dysphagia (trouble swallowing)', GIB:'Active upper GI bleed', SEPSIS:'Sepsis', HF:'Heart failure', HTN:'Hypertension', DM:'Type 2 diabetes', CKD:'Chronic kidney disease', AF:'Atrial fibrillation', ASTHMA:'Asthma', POSTOP:'Post-op', PNA:'Pneumonia'};

export const CLS_LABEL: Record<string, string> = {ACEi:'ACE inhibitor', tetracycline:'tetracycline antibiotic', BB:'beta-blocker', NSAID:'NSAID', opioid:'opioid', anticoag:'anticoagulant', statin:'statin', benzo:'benzodiazepine', steroid:'steroid', metformin:'metformin', penicillin:'penicillin', sulfonamide:'sulfonamide', codeine:'codeine', 'CCB-nd':'rate-slowing calcium channel blocker'};

/** Drugs available in "Check a new medication". */
export const CATALOG: CatalogDrug[] = [
  {key:'ibu', group:'pain',   name:'Ibuprofen', dose:'600 mg', route:'PO', freq:'q6h PRN pain', due:'PRN', cls:['NSAID']},
  {key:'keto', group:'pain',  name:'Ketorolac', dose:'15 mg', route:'IV', freq:'q6h', due:'12:00', cls:['NSAID']},
  {key:'apap', group:'pain',  name:'Acetaminophen', dose:'650 mg', route:'PO', freq:'q6h PRN pain', due:'PRN', cls:['analgesic'], apap:2600},
  {key:'tram', group:'pain',  name:'Tramadol', tall:'TraMADol', lasa:'traz', purpose:'opioid pain medicine', dose:'50 mg', route:'PO', freq:'q6h PRN pain', due:'PRN', cls:['opioid']},
  {key:'cod', group:'pain',   name:'Codeine/APAP 30/300', dose:'1 tab', route:'PO', freq:'q6h PRN pain', due:'PRN', cls:['opioid','codeine'], apap:1200},
  {key:'lora', group:'sleep-anxiety',  name:'Lorazepam', dose:'1 mg', route:'IV', freq:'q6h PRN anxiety', due:'PRN', cls:['benzo']},
  {key:'zolp', group:'sleep-anxiety',  name:'Zolpidem', dose:'5 mg', route:'PO', freq:'Nightly PRN sleep', due:'PRN', cls:['sedative']},
  {key:'prop', group:'rate-bp',  name:'Propranolol', dose:'20 mg', route:'PO', freq:'BID', due:'12:00', cls:['BB','BB-ns']},
  {key:'meto', group:'rate-bp',  name:'Metoprolol tartrate', dose:'25 mg', route:'PO', freq:'BID', due:'12:00', cls:['BB']},
  {key:'vera', group:'rate-bp',  name:'Verapamil', dose:'80 mg', route:'PO', freq:'TID', due:'12:00', cls:['CCB','CCB-nd']},
  {key:'kcl', group:'potassium',   name:'Potassium chloride', dose:'20 mEq', route:'PO', freq:'Daily', due:'12:00', cls:['Ksupp']},
  {key:'smx', group:'antibiotic',   name:'Trimethoprim-sulfamethoxazole DS', dose:'1 tab', route:'PO', freq:'BID', due:'12:00', cls:['sulfonamide','tmpsmx']},
  {key:'amox', group:'antibiotic',  name:'Amoxicillin', dose:'500 mg', route:'PO', freq:'TID', due:'12:00', cls:['penicillin']},
  {key:'cipro', group:'antibiotic', name:'Ciprofloxacin', dose:'500 mg', route:'PO', freq:'BID', due:'12:00', cls:['quinolone','QT']},
  {key:'clari', group:'antibiotic', name:'Clarithromycin', dose:'500 mg', route:'PO', freq:'BID', due:'12:00', cls:['macrolide-strong','QT']},
  {key:'fluc', group:'antifungal',  name:'Fluconazole', dose:'200 mg', route:'PO', freq:'Daily', due:'12:00', cls:['azole','QT']},
  {key:'asa', group:'antiplatelet',   name:'Aspirin', dose:'81 mg', route:'PO', freq:'Daily', due:'12:00', cls:['antiplatelet']},
  {key:'enox', group:'anticoag',  name:'Enoxaparin', dose:'40 mg', route:'SC', freq:'Daily', due:'12:00', cls:['LMWH','anticoag']},
  {key:'metf', group:'diabetes',  name:'Metformin', tall:'MetFORMIN', lasa:'metro', purpose:'diabetes medicine', dose:'500 mg', route:'PO', freq:'BID', due:'12:00', cls:['metformin']},
  {key:'glip', group:'diabetes',  name:'Glipizide', dose:'5 mg', route:'PO', freq:'Daily', due:'12:00', cls:['SU']},
  {key:'pio', group:'diabetes',   name:'Pioglitazone', dose:'15 mg', route:'PO', freq:'Daily', due:'12:00', cls:['TZD']},
  {key:'pred', group:'steroid',  name:'Prednisone', dose:'40 mg', route:'PO', freq:'Daily', due:'12:00', cls:['steroid']},
  {key:'lisi', group:'bp',  name:'Lisinopril', dose:'10 mg', route:'PO', freq:'Daily', due:'12:00', cls:['ACEi']},
  {key:'nife', group:'bp',  name:'Nifedipine ER', dose:'30 mg', route:'PO', freq:'Daily', due:'12:00', cls:['CCB','ER']},
  {key:'atorva', group:'statin',name:'Atorvastatin', dose:'40 mg', route:'PO', freq:'Nightly', due:'21:00', cls:['statin']},
  {key:'doxy', group:'antibiotic',  name:'Doxycycline', dose:'100 mg', route:'PO', freq:'BID', due:'12:00', cls:['tetracycline']},
  {key:'reglan', group:'nausea',name:'Metoclopramide', dose:'10 mg', route:'IV', freq:'q6h PRN nausea', due:'PRN', cls:['dopamine-block']},
  {key:'haldol', group:'agitation',name:'Haloperidol', dose:'2 mg', route:'IV', freq:'q6h PRN agitation', due:'PRN', cls:['dopamine-block','QT']},
  {key:'ondan', group:'nausea', name:'Ondansetron', dose:'4 mg', route:'IV', freq:'q8h PRN nausea', due:'PRN', cls:['antiemetic','QT']},
  {key:'labe', group:'bp', name:'Labetalol', dose:'100 mg', route:'PO', freq:'BID', due:'12:00', cls:['BB']},
  {key:'hydral', group:'bp', name:'Hydralazine', tall:'HydrALAZINE', lasa:'hydroxy', purpose:'blood pressure medicine', dose:'10 mg', route:'IV', freq:'q6h PRN SBP > 160', due:'PRN', cls:['vasodilator']},
  {key:'hydroxy', group:'sleep-anxiety', name:'Hydroxyzine', tall:'HydrOXYzine', lasa:'hydral', purpose:'antihistamine for anxiety or itching', dose:'25 mg', route:'PO', freq:'q6h PRN anxiety', due:'PRN', cls:['antihistamine','sedating','QT']},
  {key:'traz', group:'sleep-anxiety', name:'Trazodone', tall:'TraZODone', lasa:'tram', purpose:'antidepressant used for sleep', dose:'50 mg', route:'PO', freq:'Nightly PRN sleep', due:'PRN', cls:['sedating','QT']},
  {key:'metro', group:'antibiotic', name:'Metronidazole', tall:'MetroNIDAZOLE', lasa:'metf', purpose:'antibiotic', dose:'500 mg', route:'PO', freq:'BID', due:'12:00', cls:['nitroimidazole']},
  {key:'cephx', group:'antibiotic', name:'Cephalexin', dose:'500 mg', route:'PO', freq:'QID', due:'12:00', cls:['cephalosporin']},
  {key:'quet', group:'agitation', name:'Quetiapine', dose:'12.5 mg', route:'PO', freq:'Nightly PRN agitation', due:'PRN', cls:['antipsychotic','QT']},
  {key:'melat', group:'sleep-anxiety', name:'Melatonin', dose:'3 mg', route:'PO', freq:'Nightly PRN sleep', due:'PRN', cls:['supplement']}
];

const RAW_INFO: Record<string, [string, string, string, string]> = {
  'hydralazine':['Vasodilator','Severe high blood pressure','Low BP, fast heart rate, headache','Check BP before and 15–30 min after. Look-alike: hydrOXYzine.'],
  'hydroxyzine':['First-generation antihistamine','Anxiety, itching','Sedation, confusion in older adults, QT prolongation','Beers list for 65+. Look-alike: hydrALAZINE.'],
  'trazodone':['Antidepressant (sedating)','Sleep','Drowsiness, low BP when standing, QT prolongation','Fall precautions. Sound-alike: traMADol.'],
  'cephalexin':['Cephalosporin antibiotic (1st gen)','Skin and urinary infections','Rash, diarrhea','Low cross-reactivity with penicillin allergy.'],
  'quetiapine':['Atypical antipsychotic','Agitation, delirium (low dose)','Sedation, low BP, QT prolongation','Preferred over haloperidol in Parkinson’s disease.'],
  'melatonin':['Sleep supplement','Trouble sleeping','Morning drowsiness','Safer first choice for sleep in older adults.'],
  'lisinopril':['ACE inhibitor','High blood pressure, heart failure','Low BP, high potassium, dry cough, face or tongue swelling (angioedema)','Check BP and potassium before giving. Not for use in pregnancy.'],
  'metoprolol':['Beta-blocker (heart-selective)','Blood pressure, heart failure, heart rate control','Slow heart rate, low BP, fatigue','Check heart rate and BP before giving. Do not stop suddenly.'],
  'furosemide':['Loop diuretic','Fluid overload, heart failure','Low potassium, dehydration, low BP','Daily weight, intake and output, potassium.'],
  'spironolactone':['Potassium-sparing diuretic','Heart failure','High potassium','Check potassium and kidney function.'],
  'metformin':['Biguanide','Type 2 diabetes','Stomach upset; rare lactic acidosis','Hold before IV contrast and when kidney function is below 30.'],
  'insulin':['Rapid-acting insulin · high-alert','High blood sugar','Low blood sugar','Check glucose, give within 15 min of a meal, independent double-check.'],
  'enoxaparin':['Low-molecular-weight heparin · high-alert','Preventing blood clots','Bleeding, low platelets','Check platelets and kidney function. Do not expel the air bubble.'],
  'cefazolin':['Cephalosporin antibiotic (1st gen)','Skin and soft tissue infections','Rash, diarrhea','Low cross-reactivity with penicillin allergy.'],
  'warfarin':['Vitamin K antagonist · high-alert','Stroke prevention in atrial fibrillation','Bleeding','Check INR. Many drug and food (vitamin K) interactions.'],
  'diltiazem':['Calcium channel blocker (rate-slowing)','Heart rate control, blood pressure','Slow heart rate, low BP','Check heart rate and BP. Do not crush ER tablets.'],
  'atorvastatin':['Statin','High cholesterol','Muscle pain, liver problems','Watch for interactions with azole antifungals and some antibiotics.'],
  'acetaminophen':['Analgesic / fever reducer','Pain, fever','Liver injury above 4 g a day','Count every source, including combination pills.'],
  'morphine':['Opioid · high-alert','Severe pain','Slowed breathing, sedation, constipation','Check sedation level, RR and SpO2 before and after. Naloxone at the bedside.'],
  'ondansetron':['5-HT3 antiemetic','Nausea and vomiting','QT prolongation, headache, constipation','Safe antiemetic choice in Parkinson’s disease.'],
  'ceftriaxone':['Cephalosporin antibiotic (3rd gen)','Pneumonia, PID, other serious infections','Rash, diarrhea','Give on schedule to keep levels steady.'],
  'azithromycin':['Macrolide antibiotic','Pneumonia','QT prolongation, stomach upset','Check for other QT-prolonging drugs.'],
  'diphenhydramine':['First-generation antihistamine','Allergy, sleep','Sedation, confusion, falls in older adults','On the Beers list for patients 65+.'],
  'prednisone':['Corticosteroid','Inflammation, asthma flares','High blood sugar, mood changes, infection risk','Give with food. Check glucose in diabetes.'],
  'albuterol':['Short-acting bronchodilator','Wheezing, bronchospasm','Fast heart rate, tremor, low potassium','Check lung sounds and heart rate after.'],
  'doxycycline':['Tetracycline antibiotic','PID, some STIs, pneumonia','Esophageal irritation, sun sensitivity','Take upright with a full glass of water. Avoid in pregnancy.'],
  'metronidazole':['Nitroimidazole antibiotic','PID, anaerobic infections','Metallic taste, nausea','No alcohol during and 3 days after.'],
  'labetalol':['Alpha/beta-blocker','High blood pressure in pregnancy','Low BP, slow heart rate, dizziness','Check BP and heart rate before giving.'],
  'nifedipine':['Calcium channel blocker (dihydropyridine)','High blood pressure, including pregnancy','Headache, flushing, low BP','Do not crush the ER tablet.'],
  'prenatal':['Vitamin and mineral supplement','Pregnancy','Constipation, nausea (iron)','Separate from antacids.'],
  'carbidopa':['Dopamine precursor · time-critical','Parkinson’s disease','Nausea, low BP when standing, involuntary movements','Give within 30 min of the scheduled time. Late doses cause stiffness and swallowing problems.'],
  'ampicillin':['Penicillin + beta-lactamase inhibitor','Aspiration pneumonia, mixed infections','Allergy, rash, diarrhea','Check penicillin allergy first.'],
  'pantoprazole':['Proton pump inhibitor','Bleeding stomach ulcers','Headache, diarrhea','IV push over at least 2 minutes.'],
  'piperacillin':['Penicillin + beta-lactamase inhibitor','Sepsis, serious infections','Allergy, diarrhea, kidney effects','Draw blood cultures first. First dose within 1 hour in sepsis.'],
  'vancomycin':['Glycopeptide antibiotic','Sepsis, MRSA','Kidney injury, flushing if infused too fast','Infuse slowly (at least 60 min per gram). Dosing guided by blood levels.'],
  'amoxicillin':['Penicillin antibiotic','Ear, sinus, skin infections','Allergic reactions, diarrhea','Check penicillin allergy first.'],
  'hydrocodone':['Opioid + acetaminophen · high-alert','Moderate to severe pain','Sedation, slowed breathing, liver injury from acetaminophen','Count total daily acetaminophen.'],
  'ibuprofen':['NSAID','Pain, fever, inflammation','Stomach bleeding, kidney injury, higher BP','Avoid with warfarin, kidney disease, heart failure, GI bleed and late pregnancy.'],
  'ketorolac':['NSAID (IV)','Short-term moderate to severe pain','Stomach bleeding, kidney injury','Maximum 5 days of use.'],
  'tramadol':['Weak opioid · high-alert','Moderate pain','Seizures, serotonin syndrome, sedation','Avoid with other opioids and benzodiazepines.'],
  'codeine':['Opioid + acetaminophen · high-alert','Mild to moderate pain','Nausea, sedation; effect varies by person','Count total acetaminophen.'],
  'lorazepam':['Benzodiazepine','Anxiety, seizures','Sedation, slowed breathing, falls','Never combine with opioids without close monitoring.'],
  'zolpidem':['Sedative-hypnotic','Short-term insomnia','Falls, confusion, sleepwalking','Avoid in older adults when possible.'],
  'propranolol':['Beta-blocker (non-selective)','Blood pressure, tremor, migraine','Bronchospasm, slow heart rate','Contraindicated in asthma.'],
  'verapamil':['Calcium channel blocker (rate-slowing)','Heart rate control, blood pressure','Heart block, constipation','Avoid with beta-blockers and in heart failure.'],
  'potassium':['Electrolyte replacement (IV = high-alert)','Low potassium','High potassium, stomach irritation','Check potassium first. Never give IV push.'],
  'trimethoprim':['Sulfonamide antibiotic','Urinary and skin infections','High potassium, raises INR, rash','Check sulfa allergy first.'],
  'ciprofloxacin':['Fluoroquinolone antibiotic','Urinary and other infections','Tendon rupture, QT, confusion','Boxed warning for tendon damage.'],
  'clarithromycin':['Macrolide antibiotic','Respiratory infections, H. pylori','QT prolongation, many drug interactions','Strongly raises statin levels.'],
  'fluconazole':['Azole antifungal','Yeast infections','QT prolongation, liver effects','Strongly raises warfarin effect.'],
  'aspirin':['Antiplatelet','Heart attack and stroke prevention','Bleeding, stomach ulcers','Avoid in active GI bleeding.'],
  'glipizide':['Sulfonylurea','Type 2 diabetes','Low blood sugar','Higher risk with kidney disease and with insulin.'],
  'pioglitazone':['Thiazolidinedione','Type 2 diabetes','Fluid retention, weight gain','Boxed warning: avoid in heart failure.'],
  'metoclopramide':['Dopamine-blocking antiemetic','Nausea, slow stomach emptying','Muscle spasms, restlessness','Contraindicated in Parkinson’s disease.'],
  'haloperidol':['Antipsychotic','Agitation, delirium','Muscle stiffness, QT prolongation','Avoid in Parkinson’s disease.']
};

export const DRUG_INFO: Record<string, DrugInfo> = Object.fromEntries(
  Object.entries(RAW_INFO).map(([k, [cls, use, watch, nursing]]) => [k, { cls, use, watch, nursing }]),
);

export function drugInfoFor(name: string): DrugInfo | null {
  const n = name.toLowerCase();
  const k = Object.keys(DRUG_INFO).find(key => n.startsWith(key));
  return k ? DRUG_INFO[k] : null;
}

export const ALLERGENS: { agent: string; cls: string }[] = [
  {agent:'Penicillin', cls:'penicillin'}, {agent:'Sulfa drugs', cls:'sulfonamide'}, {agent:'Codeine', cls:'codeine'},
  {agent:'NSAIDs (ibuprofen, naproxen)', cls:'NSAID'}, {agent:'Aspirin', cls:'antiplatelet'}, {agent:'Cephalosporins', cls:'cephalosporin'},
  {agent:'Morphine / opioids', cls:'opioid'}, {agent:'Tetracyclines', cls:'tetracycline'}, {agent:'Statins', cls:'statin'},
  {agent:'Fluoroquinolones', cls:'quinolone'}, {agent:'Latex', cls:'latex'}, {agent:'Other', cls:'other'}
];

/** Legacy list kept for reference; co-signers now come from USERS. */
export const NURSES: string[] = ['RN Maria Chen', 'RN David Okafor', 'RN Sofia Reyes (charge)'];

export const BED_POOL: string[] = [];
for (let room = 410; room <= 430; room += 2) ['A', 'B'].forEach(x => BED_POOL.push(room + x));

type SeedMed = Omit<Medication, 'status' | 'at'>;
type SeedTask = Omit<CareTask, 'done' | 'at'>;
export interface SeedPatient {
  id: string; bed: string; name: string; age: number; sex: 'F' | 'M'; wt: number; dx: string;
  conditions: string[]; allergies: Allergy[]; vit: Vitals; labs: Labs; meds: SeedMed[]; tasks?: SeedTask[];
}

/** Synthetic patients (in the real build these come from Synthea via FHIR). */
export const SEED_PATIENTS: SeedPatient[] = [
    {id:'p1', bed:'412A', name:'Rosa Martínez', age:72, sex:'F', wt:68, dx:'Heart failure, hypertension', conditions:['HF','HTN'],
     allergies:[], vit:{sbp:128,dbp:76,hr:78,rr:16,spo2:96},
     labs:{k:{v:4.6,t:-420}, cr:{v:1.1,t:-420}, glu:{v:132,t:-90}},
     meds:[
      {id:'m1', name:'Lisinopril', dose:'10 mg', route:'PO', freq:'Daily', due:'09:00', cls:['ACEi'], hold:{sbp:90}, param:'Hold if SBP < 90', effect:'blood pressure'},
      {id:'m2', name:'Metoprolol succinate', dose:'25 mg', route:'PO', freq:'Daily', due:'09:00', cls:['BB'], hold:{sbp:90,hr:55}, param:'Hold if SBP < 90 or HR < 55', effect:'blood pressure and heart rate'},
      {id:'m3', name:'Furosemide', dose:'40 mg', route:'IV', freq:'BID', due:'09:00', cls:['loop']},
      {id:'m4', name:'Spironolactone', dose:'25 mg', route:'PO', freq:'Daily', due:'09:00', cls:['Ksparing']}
     ]},
    {id:'p2', bed:'412B', name:'James Thompson', age:64, sex:'M', wt:78, dx:'Type 2 diabetes, CKD stage 3, cellulitis L leg', conditions:['DM','CKD'],
     allergies:[{agent:'Penicillin', cls:'penicillin', rxn:'hives'}], vit:{sbp:138,dbp:82,hr:88,rr:18,spo2:97},
     labs:{k:{v:4.4,t:-400}, cr:{v:1.3,t:-400}, glu:{v:164,t:-60}},
     meds:[
      {id:'m1', name:'Metformin', dose:'1000 mg', route:'PO', freq:'BID', due:'09:00', cls:['metformin'], renal:true},
      {id:'m2', name:'Insulin lispro', dose:'per sliding scale', route:'SC', freq:'AC meals', due:'09:00', cls:['insulin']},
      {id:'m3', name:'Enoxaparin', dose:'40 mg', route:'SC', freq:'Daily', due:'10:00', cls:['LMWH','anticoag'], renal:true},
      {id:'m4', name:'Cefazolin', dose:'2 g', route:'IV', freq:'q8h', due:'10:00', cls:['cephalosporin']}
     ]},
    {id:'p3', bed:'414A', name:'Ana López', age:58, sex:'F', wt:70, dx:'Atrial fibrillation, anticoagulated', conditions:['AF'],
     allergies:[{agent:'Codeine', cls:'codeine', rxn:'nausea (intolerance)', intol:true}], vit:{sbp:124,dbp:78,hr:84,rr:16,spo2:98},
     labs:{k:{v:4.1,t:-380}, cr:{v:0.9,t:-380}, glu:{v:108,t:-380}, inr:{v:2.4,t:-380}},
     meds:[
      {id:'m1', name:'Warfarin', dose:'5 mg', route:'PO', freq:'Daily', due:'17:00', cls:['warfarin','anticoag']},
      {id:'m2', name:'Diltiazem ER', dose:'120 mg', route:'PO', freq:'Daily', due:'09:00', cls:['CCB','CCB-nd'], hold:{sbp:90,hr:55}, param:'Hold if SBP < 90 or HR < 55', effect:'blood pressure and heart rate'},
      {id:'m3', name:'Atorvastatin', dose:'40 mg', route:'PO', freq:'Nightly', due:'21:00', cls:['statin'], dilt:true}
     ]},
    {id:'p4', bed:'414B', name:'Marcus Davis', age:45, sex:'M', wt:88, dx:'Post-op day 1, laparoscopic appendectomy', conditions:['POSTOP'],
     allergies:[], vit:{sbp:132,dbp:80,hr:92,rr:16,spo2:97},
     labs:{k:{v:4.0,t:-300}, cr:{v:1.0,t:-300}, glu:{v:118,t:-300}},
     meds:[
      {id:'m1', name:'Acetaminophen', dose:'1000 mg', route:'PO', freq:'q6h', due:'09:00', cls:['analgesic'], apap:4000},
      {id:'m2', name:'Morphine', dose:'2 mg', route:'IV', freq:'q2h PRN pain', due:'PRN', cls:['opioid']},
      {id:'m3', name:'Ondansetron', dose:'4 mg', route:'IV', freq:'q8h PRN nausea', due:'PRN', cls:['antiemetic','QT'], qt:true},
      {id:'m4', name:'Enoxaparin', dose:'40 mg', route:'SC', freq:'Daily', due:'10:00', cls:['LMWH','anticoag'], renal:true}
     ]},
    {id:'p5', bed:'416A', name:'Grace Kim', age:81, sex:'F', wt:55, dx:'Community-acquired pneumonia', conditions:['PNA'],
     allergies:[], vit:{sbp:118,dbp:70,hr:86,rr:20,spo2:94},
     labs:{k:{v:3.9,t:-300}, cr:{v:0.8,t:-300}, glu:{v:112,t:-300}},
     meds:[
      {id:'m1', name:'Ceftriaxone', dose:'1 g', route:'IV', freq:'Daily', due:'10:00', cls:['cephalosporin']},
      {id:'m2', name:'Azithromycin', dose:'500 mg', route:'PO', freq:'Daily', due:'10:00', cls:['macrolide','QT']},
      {id:'m3', name:'Diphenhydramine', dose:'25 mg', route:'PO', freq:'Nightly PRN sleep', due:'PRN', cls:['antihistamine'], beers:true}
     ]},
    {id:'p6', bed:'416B', name:'Luis Herrera', age:37, sex:'M', wt:82, dx:'Asthma exacerbation', conditions:['ASTHMA'],
     allergies:[{agent:'Sulfa drugs', cls:'sulfonamide', rxn:'rash'}], vit:{sbp:126,dbp:78,hr:102,rr:20,spo2:95},
     labs:{k:{v:3.7,t:-240}, cr:{v:0.9,t:-240}, glu:{v:148,t:-60}},
     meds:[
      {id:'m1', name:'Prednisone', dose:'40 mg', route:'PO', freq:'Daily', due:'09:00', cls:['steroid']},
      {id:'m2', name:'Albuterol neb', dose:'2.5 mg', route:'INH', freq:'q4h', due:'10:00', cls:['bronchodilator']}
     ]},
    {id:'p7', bed:'418A', name:'Tanya Reed', age:24, sex:'F', wt:62, dx:'Pelvic inflammatory disease', conditions:['PID'],
     allergies:[], vit:{sbp:116,dbp:72,hr:96,rr:18,spo2:98},
     labs:{k:{v:3.8,t:-200}, cr:{v:0.7,t:-200}, glu:{v:96,t:-200}},
     meds:[
      {id:'m1', name:'Ceftriaxone', dose:'1 g', route:'IV', freq:'q24h', due:'10:00', cls:['cephalosporin']},
      {id:'m2', name:'Doxycycline', dose:'100 mg', route:'PO', freq:'BID', due:'09:00', cls:['tetracycline']},
      {id:'m3', name:'Metronidazole', dose:'500 mg', route:'PO', freq:'BID', due:'09:00', cls:['nitroimidazole']}
     ]},
    {id:'p8', bed:'418B', name:'Priya Shah', age:31, sex:'F', wt:74, dx:'Pregnant, 30 weeks (7 months), gestational hypertension', conditions:['PREG','HTN'],
     allergies:[], vit:{sbp:146,dbp:94,hr:92,rr:18,spo2:98},
     labs:{k:{v:4.0,t:-180}, cr:{v:0.6,t:-180}, glu:{v:102,t:-180}},
     meds:[
      {id:'m1', name:'Labetalol', dose:'200 mg', route:'PO', freq:'BID', due:'09:00', cls:['BB'], hold:{sbp:100,hr:60}, param:'Hold if SBP < 100 or HR < 60', effect:'blood pressure and heart rate'},
      {id:'m2', name:'Nifedipine ER', dose:'30 mg', route:'PO', freq:'Daily', due:'09:00', cls:['CCB','ER'], hold:{sbp:100}, param:'Hold if SBP < 100', effect:'blood pressure'},
      {id:'m3', name:'Prenatal vitamin', dose:'1 tab', route:'PO', freq:'Daily', due:'09:00', cls:['vitamin']}
     ],
     tasks:[{id:'t1', name:'Fetal heart rate check', due:35, grace:15, why:'Fetal monitoring every 4 hours is ordered at 30 weeks with high blood pressure.'}]},
    {id:'p9', bed:'420A', name:'Harold Brennan', age:76, sex:'M', wt:70, dx:"Parkinson's disease, dysphagia, aspiration pneumonia", conditions:['PD','DYSPH','PNA'],
     allergies:[], vit:{sbp:124,dbp:70,hr:80,rr:20,spo2:94},
     labs:{k:{v:4.1,t:-240}, cr:{v:1.0,t:-240}, glu:{v:110,t:-240}},
     meds:[
      {id:'m1', name:'Carbidopa-levodopa', dose:'25/100 mg', route:'PO', freq:'q4h while awake · crushed in applesauce', due:'09:00', cls:['dopaminergic'],
       tc:{due:20, grace:30, why:"Late Parkinson's doses can cause stiffness, falls and trouble swallowing within hours. Give within 30 minutes of the scheduled time."}},
      {id:'m2', name:'Ampicillin-sulbactam', dose:'3 g', route:'IV', freq:'q6h', due:'10:00', cls:['penicillin']}
     ]},
    {id:'p10', bed:'420B', name:'Robert Ellis', age:67, sex:'M', wt:80, dx:'Upper GI bleed (peptic ulcer), NPO', conditions:['GIB'],
     allergies:[], vit:{sbp:108,dbp:64,hr:104,rr:18,spo2:97},
     labs:{k:{v:4.3,t:-120}, cr:{v:1.2,t:-120}, glu:{v:118,t:-120}, hgb:{v:7.8,t:-120}},
     meds:[
      {id:'m1', name:'Pantoprazole', dose:'40 mg', route:'IV', freq:'BID', due:'09:00', cls:['PPI']},
      {id:'m2', name:'Ondansetron', dose:'4 mg', route:'IV', freq:'q8h PRN nausea', due:'PRN', cls:['antiemetic','QT'], qt:true}
     ],
     tasks:[{id:'t1', name:'Hemoglobin recheck (every 6 h)', due:30, grace:15, why:'Hemoglobin is 7.8 after an active bleed. A drop means he may need a transfusion.'}]},
    {id:'p11', bed:'422A', name:'Daniel Ortiz', age:52, sex:'M', wt:88, dx:'Sepsis, suspected urinary source', conditions:['SEPSIS'],
     allergies:[], vit:{sbp:98,dbp:58,hr:116,rr:24,spo2:94},
     labs:{k:{v:4.2,t:-30}, cr:{v:1.6,t:-30}, glu:{v:142,t:-30}, lac:{v:3.2,t:-30}},
     meds:[
      {id:'m1', name:'Piperacillin-tazobactam', dose:'4.5 g', route:'IV', freq:'q6h', due:'09:25', cls:['penicillin','antibiotic'],
       tc:{due:45, grace:0, why:'Sepsis was recognized at 08:25. Guidelines call for the first antibiotic within 1 hour, and each hour of delay raises the risk of death.'}},
      {id:'m2', name:'Vancomycin', dose:'1750 mg', route:'IV', freq:'Once (loading dose)', due:'09:25', cls:['glycopeptide'], renal:true,
       tc:{due:45, grace:0, why:'Part of the 1-hour sepsis antibiotic bundle (recognized 08:25).'}},
      {id:'m3', name:'Acetaminophen', dose:'650 mg', route:'PO', freq:'q6h PRN fever', due:'PRN', cls:['analgesic'], apap:2600}
     ],
     tasks:[{id:'t1', name:'Blood cultures x2 (before antibiotics)', due:30, grace:0, why:'Cultures must be drawn before the first antibiotic dose so the lab can identify the bacteria.'},
            {id:'t2', name:'Repeat lactate', due:105, grace:0, why:'First lactate was 3.2 mmol/L. Guidelines call for a repeat when it is above 2.'}]}
];

/** Demo accounts. In production: hospital SSO + badge tap; PINs are never stored in the frontend. */
export const USERS: (User & { pin: string })[] = [
  { username: 'jrivera', name: 'RN Jamie Rivera', role: 'nurse', title: 'Registered nurse', pin: '1234' },
  { username: 'mchen', name: 'RN Maria Chen', role: 'nurse', title: 'Registered nurse', pin: '1234' },
  { username: 'dokafor', name: 'RN David Okafor', role: 'nurse', title: 'Registered nurse', pin: '1234' },
  { username: 'sreyes', name: 'RN Sofia Reyes', role: 'charge', title: 'Charge nurse', pin: '1234' },
  { username: 'akim', name: 'Alex Kim, PharmD', role: 'pharmacist', title: 'Clinical pharmacist', pin: '1234' },
  { username: 'spatel', name: 'Dr. Samuel Patel', role: 'provider', title: 'Hospitalist (MD)', pin: '1234' },
];

export const GROUP_LABEL: Record<string, string> = {
  pain: 'pain relief', 'sleep-anxiety': 'sleep or anxiety', 'rate-bp': 'heart rate control', bp: 'blood pressure', potassium: 'potassium replacement',
  antibiotic: 'antibiotics', antifungal: 'antifungals', antiplatelet: 'antiplatelets', anticoag: 'clot prevention', diabetes: 'diabetes',
  steroid: 'steroids', statin: 'cholesterol', nausea: 'nausea', agitation: 'agitation',
};

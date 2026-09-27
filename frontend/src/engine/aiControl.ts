// Take control of AI (Assurant challenge): the same privacy + spending logic as
// backend/vital_ai/privacy.py and usage.py, so demo mode shows exactly what the server does.
import type { AiDetails, AiReason, AiUsage, Patient } from '../types';

export const PATIENT = '[PATIENT]';
export const BED = '[BED]';
export const PRICE_IN_PER_M = 3;   // USD per million input tokens (backend: VITAL_PRICE_IN)
export const PRICE_OUT_PER_M = 15; // USD per million output tokens (backend: VITAL_PRICE_OUT)
export const MODEL = 'claude-sonnet-4-5';

const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const sub = (text: string, value: string, ph: string) =>
  value.length < 2 ? text : text.replace(new RegExp(`(?<![\\p{L}\\p{N}_])${esc(value)}(?![\\p{L}\\p{N}_])`, 'giu'), ph);

/** Replace the patient's name and bed with placeholders; generalize ages over 89 (HIPAA Safe Harbor). */
export function deidentify(text: string, name: string, bed: string, age?: number): { text: string; removed: string[] } {
  let out = text;
  const removed: string[] = [];
  const parts = name.split(/\s+/).filter(x => x.length > 1).sort((a, b) => b.length - a.length);
  for (const v of [name, ...parts]) {
    const n = sub(out, v, PATIENT);
    if (n !== out) { out = n; if (!removed.includes('name')) removed.push('name'); }
  }
  const nb = sub(out, bed, BED);
  if (nb !== out) { out = nb; removed.push('bed'); }
  if (age !== undefined && age > 89) {
    const na = out.replace(new RegExp(`(?<!\\d)${age}(?=[FM]\\b|\\s*y)`, 'g'), '90+');
    if (na !== out) { out = na; removed.push('age over 89'); }
  }
  return { text: out, removed };
}

export const estimateTokens = (text: string) => Math.max(1, Math.round(text.length / 4));
export const costUsd = (tin: number, tout: number) => Math.round((tin * PRICE_IN_PER_M / 1e6 + tout * PRICE_OUT_PER_M / 1e6) * 1e6) / 1e6;

export const REASON_LABEL: Record<AiReason, string> = {
  ai: 'Rewritten by AI (de-identified)',
  off: 'AI is off: template only, nothing sent',
  'no-key': 'No AI connected: template only, nothing sent',
  budget: 'Monthly AI budget reached: template only',
  guard: 'AI answer blocked by the safety guard: template used',
  error: 'AI unavailable: template used',
};

export function money(n: number): string {
  if (n === 0) return '$0.00';
  return n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`;
}

/** In-browser ledger. Demo mode has no API key, so every request is 'no-key' (or 'off') and costs $0. */
export class AiLedger {
  private s: AiUsage = {
    mode: 'on', budgetUsd: 5, calls: 0, aiCalls: 0, templateCalls: 0, blocked: 0, tokensIn: 0, tokensOut: 0, costUsd: 0,
    overBudget: false, keyConfigured: false, model: MODEL, priceInPerM: PRICE_IN_PER_M, priceOutPerM: PRICE_OUT_PER_M, recent: [],
  };

  request(kind: string, template: string, p: Patient): AiDetails {
    const { text, removed } = deidentify(template, p.name, p.bed, p.age);
    const reason: AiReason = this.s.mode === 'off' ? 'off' : 'no-key';
    const d: AiDetails = { kind, model: MODEL, sentText: text, removed, deidentified: true, tokensIn: estimateTokens(text) + 60, tokensOut: 0, costUsd: 0, estimated: true, reason };
    this.s.calls++; this.s.templateCalls++;
    this.s.recent = [{ at: Date.now() / 1000, kind, reason, tokens: d.tokensIn, costUsd: 0, deidentified: true }, ...this.s.recent].slice(0, 10);
    return d;
  }

  set(x: { mode?: 'on' | 'off'; budgetUsd?: number }): AiUsage {
    if (x.mode === 'on' || x.mode === 'off') this.s.mode = x.mode;
    if (x.budgetUsd !== undefined && x.budgetUsd >= 0) this.s.budgetUsd = Math.round(x.budgetUsd * 100) / 100;
    return this.summary();
  }

  summary(): AiUsage {
    return { ...this.s, overBudget: this.s.costUsd >= this.s.budgetUsd, recent: [...this.s.recent] };
  }
}

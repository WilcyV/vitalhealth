import type { Alert, Severity } from '../types';

export function Chip({ kind, children, pulse, title }: { kind: 'crit' | 'warn' | 'ok' | 'info' | 'neutral'; children: React.ReactNode; pulse?: boolean; title?: string }) {
  return <span className={`chip ${kind}`} title={title}>{pulse && <span className="dot" />}{children}</span>;
}

export const sevLabel = (s: Severity) => (s === 'crit' ? 'Critical' : s === 'warn' ? 'Warning' : 'Low');

export function PatientStatus({ alerts, pid }: { alerts: Alert[]; pid: string }) {
  const mine = alerts.filter(a => a.pid === pid);
  const c = mine.filter(a => a.sev === 'crit').length, w = mine.filter(a => a.sev === 'warn').length;
  if (c) return <Chip kind="crit" pulse>{c} critical</Chip>;
  if (w) return <Chip kind="warn">{w} warning{w > 1 ? 's' : ''}</Chip>;
  return <Chip kind="ok">Stable</Chip>;
}

export function Sparkline({ data, lo, hi, threshold, color }: { data: number[]; lo: number; hi: number; threshold?: number; color: string }) {
  const W = 120, H = 30, pad = 3, n = data.length;
  if (n < 2) return null;
  const y = (v: number) => pad + (1 - (Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo)) * (H - 2 * pad);
  const x = (i: number) => (i / (n - 1)) * W;
  const pts = data.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
  const area = `M0,${H} L${pts.join(' L')} L${W},${H} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
      <path d={area} fill={color} opacity={0.12} />
      {threshold != null && <line x1={0} x2={W} y1={y(threshold)} y2={y(threshold)} stroke="var(--crit)" strokeWidth={1} strokeDasharray="3 3" opacity={0.6} />}
      <polyline points={pts.join(' ')} fill="none" stroke={color} strokeWidth={1.6} vectorEffect="non-scaling-stroke" />
      <circle cx={x(n - 1)} cy={y(data[n - 1])} r={2.6} fill={color} />
    </svg>
  );
}

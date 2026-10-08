// Effort vs likely recovery for every open case, in the same Recharts/shadcn style as AreaTrend.
// Bubble size = risk; colour = in today's plan / exploration / not picked; dashed line = capacity.
import { CartesianGrid, Label, LabelList, ReferenceArea, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts';
import { inr } from '../lib/format';
import type { QueueCase } from '../lib/types';

const GROUPS = [
  { key: 'plan', label: "In today's plan", color: 'var(--series-1)', test: (c: QueueCase) => c.selected && !c.exploration },
  { key: 'explore', label: 'Exploration', color: 'var(--series-2)', test: (c: QueueCase) => c.selected && c.exploration },
  { key: 'rest', label: 'Not picked', color: 'var(--mark-muted)', test: (c: QueueCase) => !c.selected },
] as const;

type Pt = QueueCase & { x: number; y: number };

function Tip({ active, payload }: { active?: boolean; payload?: { payload: Pt }[] }) {
  const c = payload?.[0]?.payload;
  if (!active || !c) return null;
  const g = GROUPS.find(x => x.test(c))!;
  return (
    <div className="chart-tip" style={{ maxWidth: 280 }}>
      <div className="chart-tip-label">{c.title}</div>
      <div className="chart-tip-row"><i style={{ background: g.color }} /><span>{g.label}</span></div>
      <div className="chart-tip-row"><span>Likely recovered</span><b>{inr(c.expected_recovery)}</b></div>
      <div className="chart-tip-row"><span>Effort</span><b>{c.effort_hours}h</b></div>
      <div className="chart-tip-row"><span>Risk</span><b>{c.risk}</b></div>
      <div className="chart-tip-row total"><span>₹ per hour</span><b>{inr(c.recovery_per_hour)}</b></div>
    </div>
  );
}

export function PortfolioChart({ cases, capacity, onPick }: { cases: QueueCase[]; capacity: number; onPick?: (id: string) => void }) {
  const pts: Pt[] = cases.map(c => ({ ...c, x: c.effort_hours, y: c.expected_recovery }));
  const xMax = Math.ceil(Math.max(capacity * 1.08, ...pts.map(p => p.x + 4)) / 10) * 10;
  return (
    <div>
      <div className="area-legend" style={{ justifyContent: 'flex-start', marginBottom: 6 }}>
        {GROUPS.map(g => <span key={g.key}><i style={{ background: g.color, borderRadius: '50%' }} />{g.label}</span>)}
        <span className="muted">· bubble size = risk</span>
      </div>
      <div style={{ height: 320 }} className="pf-chart">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 22, right: 28, bottom: 4, left: 4 }}>
            <defs>
              {GROUPS.map(g => (
                <radialGradient key={g.key} id={`pf-${g.key}`} cx="35%" cy="30%" r="75%">
                  <stop offset="0%" stopColor="#fff" stopOpacity={0.55} />
                  <stop offset="45%" stopColor={g.color} stopOpacity={0.95} />
                  <stop offset="100%" stopColor={g.color} stopOpacity={1} />
                </radialGradient>
              ))}
              <linearGradient id="pf-cap" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.02} />
                <stop offset="100%" stopColor="var(--accent)" stopOpacity={0.09} />
              </linearGradient>
              <filter id="pf-glow" x="-50%" y="-50%" width="200%" height="200%">
                <feDropShadow dx="0" dy="3" stdDeviation="4" floodColor="var(--accent)" floodOpacity="0.35" />
              </filter>
            </defs>
            <CartesianGrid vertical={false} stroke="var(--grid)" strokeDasharray="4 6" />
            <ReferenceArea x1={0} x2={capacity} fill="url(#pf-cap)" />
            <XAxis type="number" dataKey="x" domain={[0, xMax]} ticks={Array.from({ length: xMax / 10 + 1 }, (_, i) => i * 10)} tickLine={false} axisLine={{ stroke: 'var(--axis)' }} tickMargin={8}
              tickFormatter={v => `${v}h`} tick={{ fill: 'var(--text-3)', fontSize: 12 }} />
            <YAxis type="number" dataKey="y" tickLine={false} axisLine={false} width={64} tickFormatter={v => inr(v)} tick={{ fill: 'var(--text-3)', fontSize: 12 }} />
            <ZAxis type="number" dataKey="risk" range={[110, 520]} domain={[0, 100]} />
            <ReferenceLine x={capacity} stroke="var(--accent)" strokeDasharray="6 5" strokeWidth={1.5}>
              <Label value={`Your capacity · ${capacity}h`} position="insideTopRight" fill="var(--accent)" fontSize={11} fontWeight={700} offset={8} />
            </ReferenceLine>
            <Tooltip cursor={false} content={<Tip />} />
            {GROUPS.map(g => (
              <Scatter key={g.key} name={g.label} data={pts.filter(g.test)} fill={`url(#pf-${g.key})`} stroke="var(--chart-surface)" strokeWidth={2.5}
                filter={g.key === 'rest' ? undefined : 'url(#pf-glow)'} fillOpacity={g.key === 'rest' ? 0.85 : 1}
                animationDuration={700} cursor={onPick ? 'pointer' : undefined} onClick={(p: { payload?: Pt }) => p.payload && onPick?.(p.payload.case_id)}>
                {g.key !== 'rest' && <LabelList dataKey="case_id" content={(props: { x?: number | string; y?: number | string; width?: number | string; value?: unknown }) => {
                  const x = Number(props.x) + Number(props.width ?? 0) + 8, y = Number(props.y) + Number(props.width ?? 0) / 2;
                  const t = String(props.value).replace('CASE-', '#');
                  return <g pointerEvents="none"><rect x={x} y={y - 10} width={t.length * 7 + 12} height={20} rx={10} fill="var(--surface)" stroke="var(--line-strong)" />
                    <text x={x + 6} y={y + 4} fontSize={11} fontWeight={650} fill="var(--text)">{t}</text></g>;
                }} />}
              </Scatter>
            ))}
          </ScatterChart>
        </ResponsiveContainer>
        <span className="pf-hint">More ₹, fewer hours ↖</span>
      </div>
    </div>
  );
}

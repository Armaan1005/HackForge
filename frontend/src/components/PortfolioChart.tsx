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
      <div style={{ height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 18, right: 24, bottom: 4, left: 4 }}>
            <CartesianGrid stroke="var(--grid)" />
            <ReferenceArea x1={0} x2={capacity} fill="var(--accent)" fillOpacity={0.04} />
            <XAxis type="number" dataKey="x" domain={[0, xMax]} ticks={Array.from({ length: xMax / 10 + 1 }, (_, i) => i * 10)} tickLine={false} axisLine={false} tickMargin={8}
              tickFormatter={v => `${v}h`} tick={{ fill: 'var(--text-3)', fontSize: 12 }} />
            <YAxis type="number" dataKey="y" tickLine={false} axisLine={false} width={64} tickFormatter={v => inr(v)} tick={{ fill: 'var(--text-3)', fontSize: 12 }} />
            <ZAxis type="number" dataKey="risk" range={[90, 420]} domain={[0, 100]} />
            <ReferenceLine x={capacity} stroke="var(--accent)" strokeDasharray="5 5" strokeWidth={1.5}>
              <Label value={`Your capacity · ${capacity}h`} position="insideTopRight" fill="var(--accent)" fontSize={11} fontWeight={650} />
            </ReferenceLine>
            <Tooltip cursor={{ strokeDasharray: '3 3', stroke: 'var(--axis)' }} content={<Tip />} />
            {GROUPS.map(g => (
              <Scatter key={g.key} name={g.label} data={pts.filter(g.test)} fill={g.color} stroke="var(--chart-surface)" strokeWidth={2}
                cursor={onPick ? 'pointer' : undefined} onClick={(p: { payload?: Pt }) => p.payload && onPick?.(p.payload.case_id)}>
                {g.key !== 'rest' && <LabelList dataKey="case_id" position="right" offset={10} formatter={(v: unknown) => String(v).replace('CASE-', '#')}
                  style={{ fill: 'var(--text-2)', fontSize: 11, fontWeight: 600 }} />}
              </Scatter>
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

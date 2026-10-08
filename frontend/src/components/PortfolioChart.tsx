// Effort vs likely recovery for every open case, laid out like shadcn/ui's interactive charts
// (ui.shadcn.com/charts): header with clickable group totals, flat marks, horizontal grid only,
// dot-indicator tooltip, and a footer summary. Built on Recharts, as shadcn's charts are.
import { useState } from 'react';
import { CartesianGrid, LabelList, ReferenceArea, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts';
import { inr } from '../lib/format';
import type { QueueCase } from '../lib/types';
import { Icon } from './Icon';

const GROUPS = [
  { key: 'plan', label: "Today's plan", color: 'var(--series-1)', test: (c: QueueCase) => c.selected && !c.exploration },
  { key: 'explore', label: 'Exploration', color: 'var(--series-2)', test: (c: QueueCase) => c.selected && c.exploration },
  { key: 'rest', label: 'Not picked', color: 'var(--mark-muted)', test: (c: QueueCase) => !c.selected },
] as const;
type GroupKey = typeof GROUPS[number]['key'];
type Pt = QueueCase & { x: number; y: number };

function Tip({ active, payload }: { active?: boolean; payload?: { payload: Pt }[] }) {
  const c = payload?.[0]?.payload;
  if (!active || !c) return null;
  const g = GROUPS.find(x => x.test(c))!;
  return (
    <div className="chart-tip" style={{ maxWidth: 260 }}>
      <div className="chart-tip-label">{c.case_id.replace('CASE-', '#')} · {c.title}</div>
      <div className="chart-tip-row"><i style={{ background: g.color, borderRadius: '50%' }} /><span>{g.label}</span></div>
      <div className="chart-tip-row"><span>Likely recovered</span><b>{inr(c.expected_recovery)}</b></div>
      <div className="chart-tip-row"><span>Effort</span><b>{c.effort_hours}h</b></div>
      <div className="chart-tip-row"><span>Risk</span><b>{c.risk}</b></div>
      <div className="chart-tip-row total"><span>Per hour</span><b>{inr(c.recovery_per_hour)}</b></div>
    </div>
  );
}

export function PortfolioChart({ cases, capacity, onPick }: { cases: QueueCase[]; capacity: number; onPick?: (id: string) => void }) {
  const [focus, setFocus] = useState<GroupKey | null>(null);
  const pts: Pt[] = cases.map(c => ({ ...c, x: c.effort_hours, y: c.expected_recovery }));
  const xMax = Math.ceil(Math.max(capacity + 4, ...pts.map(p => p.x + 4)) / 10) * 10;
  const totals = GROUPS.map(g => {
    const list = pts.filter(g.test);
    return { ...g, n: list.length, money: list.reduce((s, c) => s + c.expected_recovery, 0), hours: list.reduce((s, c) => s + c.effort_hours, 0) };
  });
  const picked = totals[0].hours + totals[1].hours, pickedMoney = totals[0].money + totals[1].money;
  const dim = (k: GroupKey) => (focus && focus !== k ? 0.18 : 1);

  return (
    <div className="pc">
      <div className="pc-head">
        <div className="pc-title">
          <h2>Where today's hours go</h2>
          <p className="small muted">Likely recovery against hours to investigate, for all {cases.length} open cases</p>
        </div>
        <div className="pc-totals" role="group" aria-label="Highlight a group">
          {totals.map(t => (
            <button key={t.key} type="button" className={focus === t.key ? 'on' : ''} aria-pressed={focus === t.key}
              onClick={() => setFocus(f => (f === t.key ? null : t.key))}>
              <span className="pc-total-label"><i style={{ background: t.color }} />{t.label}</span>
              <b>{inr(t.money)}</b>
              <span className="pc-total-sub">{t.n} case{t.n === 1 ? '' : 's'} · {t.hours}h</span>
            </button>
          ))}
        </div>
      </div>

      <div className="pc-plot">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 20, right: 20, bottom: 0, left: 0 }}>
            <defs>
              <pattern id="pc-over" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <line x1="0" y1="0" x2="0" y2="6" stroke="var(--text-3)" strokeWidth="1" strokeOpacity="0.18" />
              </pattern>
            </defs>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <ReferenceArea x1={capacity} x2={xMax} fill="url(#pc-over)" ifOverflow="hidden"
              label={{ value: 'Over capacity', position: 'insideTopRight', fill: 'var(--text-3)', fontSize: 11 }} />
            <XAxis type="number" dataKey="x" domain={[0, xMax]} ticks={Array.from({ length: xMax / 10 + 1 }, (_, i) => i * 10)}
              tickLine={false} axisLine={false} tickMargin={10} tickFormatter={v => `${v}h`} tick={{ fill: 'var(--text-3)', fontSize: 12 }} />
            <YAxis type="number" dataKey="y" tickLine={false} axisLine={false} width={60} tickMargin={6} tickFormatter={v => inr(v)} tick={{ fill: 'var(--text-3)', fontSize: 12 }} />
            <ZAxis type="number" dataKey="risk" range={[70, 300]} domain={[0, 100]} />
            <ReferenceLine x={capacity} stroke="var(--text-2)" strokeWidth={1}
              label={{ value: `${capacity}h available`, position: 'top', fill: 'var(--text)', fontSize: 11, fontWeight: 600 }} />
            <Tooltip cursor={false} content={<Tip />} />
            {totals.map(g => (
              <Scatter key={g.key} name={g.label} data={pts.filter(g.test)} fill={g.color} fillOpacity={dim(g.key) * (g.key === 'rest' ? 0.9 : 1)}
                stroke="var(--chart-surface)" strokeWidth={2} strokeOpacity={dim(g.key)} isAnimationActive={false}
                cursor={onPick ? 'pointer' : undefined} onClick={(p: { payload?: Pt }) => p.payload && onPick?.(p.payload.case_id)}>
                {g.key !== 'rest' && <LabelList dataKey="case_id" position="right" offset={10} formatter={(v: unknown) => String(v).replace('CASE-', '#')}
                  style={{ fill: 'var(--text)', fontSize: 12, fontWeight: 600, opacity: dim(g.key) }} />}
              </Scatter>
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <div className="pc-foot">
        <b><Icon name="trend-up" size={15} className="inline" /> {inr(pickedMoney)} likely recovered in {picked} of {capacity} hours</b>
        <span className="small muted">Cases picked to get the most back from the hours available. Dot size shows risk; click a dot to open the case.</span>
      </div>
    </div>
  );
}

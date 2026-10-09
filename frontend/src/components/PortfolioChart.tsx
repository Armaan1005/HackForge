// "Value curve" for the Cases page, in the shadcn/ui chart style (ui.shadcn.com/charts) on Recharts:
// today's picks first, then the rest by ₹ per hour, along the x axis (hours), cumulative likely recovery on the y axis. The curve climbs
// fast while the best cases are added, then flattens. Gradient fill, one dot per case coloured by plan status,
// capacity line, and a draw-in animation whenever the data changes. Header totals highlight a group.
import { useState } from 'react';
import { Area, ComposedChart, CartesianGrid, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { inr } from '../lib/format';
import type { QueueCase } from '../lib/types';
import { Icon } from './Icon';

const GROUPS = [
  { key: 'plan', label: "Today's plan", color: 'var(--series-1)', test: (c: QueueCase) => c.selected && !c.exploration },
  { key: 'explore', label: 'Exploration', color: 'var(--series-2)', test: (c: QueueCase) => c.selected && c.exploration },
  { key: 'rest', label: 'Not picked', color: '#b9b9b2', test: (c: QueueCase) => !c.selected },
] as const;
type GroupKey = typeof GROUPS[number]['key'];
type Pt = { h: number; total: number; c?: QueueCase; g?: typeof GROUPS[number] };

function Tip({ active, payload }: { active?: boolean; payload?: { payload: Pt }[] }) {
  const p = payload?.[0]?.payload;
  if (!active || !p?.c || !p.g) return null;
  return (
    <div className="chart-tip" style={{ maxWidth: 270 }}>
      <div className="chart-tip-label">{p.c.case_id.replace('CASE-', '#')} · {p.c.title}</div>
      <div className="chart-tip-row"><i style={{ background: p.g.color, borderRadius: '50%' }} /><span>{p.g.label}</span></div>
      <div className="chart-tip-row"><span>Adds</span><b>{inr(p.c.expected_recovery)}</b></div>
      <div className="chart-tip-row"><span>Takes</span><b>{p.c.effort_hours}h</b></div>
      <div className="chart-tip-row"><span>Per hour</span><b>{inr(p.c.recovery_per_hour)}</b></div>
      <div className="chart-tip-row total"><span>Running total at {p.h}h</span><b>{inr(p.total)}</b></div>
    </div>
  );
}

export function PortfolioChart({ cases, capacity, onPick }: { cases: QueueCase[]; capacity: number; onPick?: (id: string) => void }) {
  const [focus, setFocus] = useState<GroupKey | null>(null);
  // Plan order: today's picks first (exploration last among them), then everything else by ₹ per hour.
  // Built from the cases themselves so every green dot lands inside the capacity line.
  const order = [...cases].sort((x, y) => (+y.selected - +x.selected) || (+x.exploration - +y.exploration) || (y.recovery_per_hour - x.recovery_per_hour));
  const pts: Pt[] = [{ h: 0, total: 0 }];
  for (const c of order) {
    const last = pts[pts.length - 1];
    pts.push({ h: last.h + c.effort_hours, total: last.total + c.expected_recovery, c, g: GROUPS.find(g => g.test(c)) });
  }
  const xMax = Math.ceil(Math.max(capacity + 6, ...pts.map(p => p.h)) / 10) * 10;
  const totals = GROUPS.map(g => {
    const list = cases.filter(g.test);
    return { ...g, n: list.length, money: list.reduce((s, c) => s + c.expected_recovery, 0), hours: list.reduce((s, c) => s + c.effort_hours, 0) };
  });
  const picked = totals[0].hours + totals[1].hours, pickedMoney = totals[0].money + totals[1].money;

  const Dot = (props: { cx?: number; cy?: number; payload?: Pt; index?: number }) => {
    const { cx, cy, payload: p } = props;
    if (cx == null || cy == null || !p?.c || !p.g) return <g />;
    const faded = focus && focus !== p.g.key;
    const big = p.g.key !== 'rest';
    return (
      <g style={{ cursor: onPick ? 'pointer' : 'default', opacity: faded ? 0.2 : 1, transition: 'opacity .25s' }} onClick={() => onPick?.(p.c!.case_id)}>
        {big && <circle cx={cx} cy={cy} r={11} fill={p.g.color} opacity={0.16} className="vc-pulse" />}
        <circle cx={cx} cy={cy} r={big ? 6 : 4.5} fill={p.g.color} stroke="var(--chart-surface)" strokeWidth={2} />
        {big && <text x={cx + 10} y={cy - 9} fontSize={11} fontWeight={650} fill="var(--text)">{p.c.case_id.replace('CASE-', '#')}</text>}
      </g>
    );
  };

  return (
    <div className="pc">
      <div className="pc-head">
        <div className="pc-title">
          <h2>Where today's hours go</h2>
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
          <ComposedChart data={pts} margin={{ top: 24, right: 24, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="vc-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--series-1)" stopOpacity={0.45} />
                <stop offset="100%" stopColor="var(--series-1)" stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="vc-line" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#3fae7f" />
                <stop offset={`${Math.min(100, (capacity / xMax) * 100)}%`} stopColor="var(--series-1)" />
                <stop offset={`${Math.min(100, (capacity / xMax) * 100)}%`} stopColor="#b9b9b2" />
                <stop offset="100%" stopColor="#b9b9b2" />
              </linearGradient>
              <pattern id="vc-over" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <line x1="0" y1="0" x2="0" y2="6" stroke="var(--text-3)" strokeWidth="1" strokeOpacity="0.16" />
              </pattern>
            </defs>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <ReferenceArea x1={capacity} x2={xMax} fill="url(#vc-over)" ifOverflow="hidden"
              label={{ value: 'Over capacity', position: 'insideTopRight', fill: 'var(--text-3)', fontSize: 11 }} />
            <XAxis type="number" dataKey="h" domain={[0, xMax]} ticks={Array.from({ length: Math.floor(xMax / 20) + 1 }, (_, i) => i * 20)}
              tickLine={false} axisLine={false} tickMargin={10} tickFormatter={v => `${v}h`} tick={{ fill: 'var(--text-3)', fontSize: 12 }} />
            <YAxis tickLine={false} axisLine={false} width={60} tickMargin={6} tickFormatter={v => inr(v)} tick={{ fill: 'var(--text-3)', fontSize: 12 }} />
            <ReferenceLine x={capacity} stroke="var(--text-2)" strokeWidth={1}
              label={{ value: `${capacity}h available`, position: 'top', fill: 'var(--text)', fontSize: 11, fontWeight: 600 }} />
            <Tooltip cursor={{ stroke: 'var(--axis)', strokeDasharray: '3 3' }} content={<Tip />} />
            <Area key={capacity} type="monotone" dataKey="total" stroke="url(#vc-line)" strokeWidth={3} fill="url(#vc-fill)"
              dot={<Dot />} activeDot={false} isAnimationActive animationDuration={1100} animationEasing="ease-out" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="pc-foot">
        <b><Icon name="trend-up" size={15} className="inline" /> {inr(pickedMoney)} likely recovered in {picked} of {capacity} hours</b>
        <span className="small muted">Steep early, flat later: the first hours recover the most. Green dots are in today's plan; click a dot to open the case.</span>
      </div>
    </div>
  );
}

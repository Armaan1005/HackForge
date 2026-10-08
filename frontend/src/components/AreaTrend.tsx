// shadcn/ui "Area Chart - Interactive" (ui.shadcn.com/charts/area), ported to Axon: Recharts, gradient fills,
// time-range picker, dot-indicator tooltip, legend. Colours are the validated --series-1 / --series-2 pair.
import { useId, useMemo, useState } from 'react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Claim } from '../lib/types';
import { inr } from '../lib/format';
import { Segmented } from './ui';

export interface Week { week: string; paid: number; pending: number }
const SERIES = [
  { key: 'paid', label: 'Already paid', color: 'var(--series-2)' },
  { key: 'pending', label: 'Still pending', color: 'var(--series-1)' },
] as const;

/** Billed amount per week (Monday start), split into paid vs still pending. Denied claims are left out. */
export function weekly(claims: Claim[]): Week[] {
  const by = new Map<string, Week>();
  for (const c of claims) {
    if (c.payment_status === 'denied') continue;
    const d = new Date(`${c.service_date.slice(0, 10)}T00:00:00`);
    d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const w = by.get(key) ?? { week: key, paid: 0, pending: 0 };
    w[c.payment_status === 'paid' ? 'paid' : 'pending'] += c.billed_amount;
    by.set(key, w);
  }
  return [...by.values()].sort((a, b) => a.week.localeCompare(b.week));
}

const short = (d: string) => new Date(`${d}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });

function TipBox({ active, payload, label }: { active?: boolean; payload?: { dataKey: string; value: number }[]; label?: string }) {
  if (!active || !payload?.length || !label) return null;
  const total = payload.reduce((s, p) => s + p.value, 0);
  return (
    <div className="chart-tip">
      <div className="chart-tip-label">Week of {short(label)}</div>
      {[...SERIES].reverse().map(s => {
        const p = payload.find(x => x.dataKey === s.key);
        return p ? <div key={s.key} className="chart-tip-row"><i style={{ background: s.color }} /><span>{s.label}</span><b>{inr(p.value)}</b></div> : null;
      })}
      <div className="chart-tip-row total"><span>Total billed</span><b>{inr(total)}</b></div>
    </div>
  );
}

export function AreaTrend({ title, description, data, today, source, height = 260 }: { title: string; description: string; data: Week[]; today: string; source: string; height?: number }) {
  const id = useId().replace(/:/g, '');
  const [range, setRange] = useState<'90' | '180' | 'all'>('all');
  const shown = useMemo(() => {
    if (range === 'all') return data;
    const from = new Date(`${today}T00:00:00`); from.setDate(from.getDate() - Number(range));
    return data.filter(w => new Date(`${w.week}T00:00:00`) >= from);
  }, [data, range, today]);

  return (
    <div className="card area-card">
      <div className="area-head">
        <div><h2>{title}</h2><p className="small muted">{description}</p></div>
        <Segmented size="sm" label="Time range" value={range} onChange={setRange}
          options={[{ value: '90', label: '3 months' }, { value: '180', label: '6 months' }, { value: 'all', label: 'All' }]} />
      </div>
      {shown.length === 0 ? <p className="muted small" style={{ padding: '40px 0', textAlign: 'center' }}>No claims in this range.</p> : (
        <div style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={shown} margin={{ left: 4, right: 12, top: 8, bottom: 0 }}>
              <defs>
                {SERIES.map(s => (
                  <linearGradient key={s.key} id={`${id}-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={s.color} stopOpacity={0.8} />
                    <stop offset="95%" stopColor={s.color} stopOpacity={0.1} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid vertical={false} stroke="var(--grid)" />
              <XAxis dataKey="week" tickLine={false} axisLine={false} tickMargin={8} minTickGap={32} tickFormatter={short} tick={{ fill: 'var(--text-3)', fontSize: 12 }} />
              <YAxis tickLine={false} axisLine={false} width={58} tickFormatter={v => inr(v)} tick={{ fill: 'var(--text-3)', fontSize: 12 }} />
              <Tooltip cursor={{ stroke: 'var(--axis)', strokeWidth: 1 }} content={<TipBox />} />
              {SERIES.map(s => (
                <Area key={s.key} dataKey={s.key} name={s.label} type="natural" stackId="a" fill={`url(#${id}-${s.key})`} stroke={s.color} strokeWidth={2}
                  activeDot={{ r: 4, stroke: 'var(--surface)', strokeWidth: 2 }} />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
      <div className="area-foot">
        <span />
        <div className="area-legend">
          {[...SERIES].reverse().map(s => <span key={s.key}><i style={{ background: s.color }} />{s.label}</span>)}
        </div>
        <span className="area-source" title={`${source}\nWeekly sums of billed_amount by service_date (week starts Monday); denied claims left out.`}>
          Source: {source}
        </span>
      </div>
    </div>
  );
}

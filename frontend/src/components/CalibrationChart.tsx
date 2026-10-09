// Forecast calibration in the same Recharts style as the Cases value curve: predicted (x) vs observed (y),
// dashed diagonal = perfect, observed curve with a gradient, dots sized by how many cases sit in each bin.
// Bins with very few cases are drawn faint so a 2-case outlier doesn't read as a failure.
import { Area, ComposedChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis, ZAxis } from 'recharts';
import { num } from '../lib/format';

type Bin = { bin: string; predicted: number; observed: number; n: number };
const SMALL = 5;

function Tip({ active, payload }: { active?: boolean; payload?: { payload: Bin & { x: number; y: number } }[] }) {
  const b = payload?.find(p => p.payload?.n != null)?.payload;
  if (!active || !b) return null;
  return (
    <div className="chart-tip">
      <div className="chart-tip-label">Predicted {b.bin.replace('-', '–')}</div>
      <div className="chart-tip-row"><i style={{ background: 'var(--series-1)', borderRadius: '50%' }} /><span>Predicted</span><b>{Math.round(b.predicted * 100)}%</b></div>
      <div className="chart-tip-row"><span>Actually happened</span><b>{Math.round(b.observed * 100)}%</b></div>
      <div className="chart-tip-row total"><span>Cases in this bin</span><b>{num(b.n)}</b></div>
      {b.n < SMALL && <div className="xs faint" style={{ marginTop: 4 }}>Too few cases to judge this bin.</div>}
    </div>
  );
}

export function CalibrationChart({ bins }: { bins: Bin[] }) {
  const pts = [...bins].sort((a, b) => a.predicted - b.predicted).map(b => ({ ...b, x: b.predicted, y: b.observed, z: Math.log10(b.n + 1) }));
  const big = pts.filter(p => p.n >= SMALL), small = pts.filter(p => p.n < SMALL);
  const pct = (v: number) => `${Math.round(v * 100)}%`;
  return (
    <div>
      <div style={{ height: 250 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={pts} margin={{ top: 12, right: 18, bottom: 0, left: -6 }}>
            <defs>
              <linearGradient id="cal-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--series-1)" stopOpacity={0.32} />
                <stop offset="100%" stopColor="var(--series-1)" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="var(--grid)" />
            <XAxis type="number" dataKey="x" domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} tickFormatter={pct} tickLine={false} axisLine={false}
              tickMargin={8} tick={{ fill: 'var(--text-3)', fontSize: 11 }} />
            <YAxis type="number" dataKey="y" domain={[0, 1]} ticks={[0, 0.5, 1]} tickFormatter={pct} tickLine={false} axisLine={false}
              width={44} tick={{ fill: 'var(--text-3)', fontSize: 11 }} />
            <ZAxis type="number" dataKey="z" range={[40, 260]} />
            <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="var(--axis)" strokeDasharray="5 5" strokeWidth={1.5}
              label={{ value: 'perfect', position: 'insideTopLeft', fill: 'var(--text-3)', fontSize: 10, dy: 30, dx: 6 }} />
            <Tooltip cursor={{ stroke: 'var(--axis)', strokeDasharray: '3 3' }} content={<Tip />} />
            <Area type="monotone" dataKey="y" data={big} stroke="var(--series-1)" strokeWidth={2.5} fill="url(#cal-fill)" dot={false} activeDot={false}
              isAnimationActive animationDuration={900} />
            <Scatter data={big} fill="var(--series-1)" stroke="var(--chart-surface)" strokeWidth={2} />
            <Scatter data={small} fill="var(--series-1)" fillOpacity={0.28} stroke="var(--series-1)" strokeOpacity={0.5} strokeWidth={1} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="xs faint" style={{ marginTop: 6 }}>Predicted vs what actually happened. On the dashed line is perfect; bigger dots hold more cases, faint dots have fewer than {SMALL}.</p>
    </div>
  );
}

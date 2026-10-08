// Lightweight SVG charts. Rules (dataviz skill): one axis, thin marks with 4px rounded data-ends,
// single-series = one hue and no legend, >=2 series = legend + direct labels, text in ink colours,
// hover tooltip on every mark, recessive grid.
import { motion } from 'motion/react';
import { useMemo } from 'react';
import { inr, num } from '../lib/format';
import { useWidth } from '../lib/hooks';
import type { QueueCase } from '../lib/types';
import { useTooltip } from './ui';

// Ordinal blue ramp (reference palette steps 250 -> 550) for funnel stages.
const ORDINAL = ['#86b6ef', '#6da7ec', '#5598e7', '#3987e5', '#2a78d6', '#1c5cab'];

export function Funnel({ stages }: { stages: { label: string; value: number; note?: string }[] }) {
  const tip = useTooltip();
  const max = Math.max(...stages.map(s => s.value), 1);
  return (
    <div role="list" aria-label="Alert funnel">
      {stages.map((s, i) => {
        // log scale so 50,000 and 12 are both visible; the label carries the true number
        const w = Math.max((Math.log10(s.value + 1) / Math.log10(max + 1)) * 100, 2);
        return (
          <div key={s.label} className="funnel-row" role="listitem" {...tip.bind(<><b>{s.label}</b><br />{num(s.value)}{s.note ? <><br /><span className="muted">{s.note}</span></> : null}</>)}>
            <span className="small muted">{s.label}</span>
            <div style={{ borderLeft: '1px solid var(--axis)' }}>
              <motion.div className="funnel-bar" style={{ background: ORDINAL[Math.min(i, ORDINAL.length - 1)] }}
                initial={{ width: 0 }} animate={{ width: `${w}%` }} transition={{ duration: 0.7, delay: i * 0.06, ease: [0.22, 1, 0.36, 1] }} />
            </div>
            <span className="tabular strong" style={{ textAlign: 'right' }}>{num(s.value)}</span>
          </div>
        );
      })}
      <div className="xs faint" style={{ marginTop: 6 }}>Bar length on a log scale; numbers are exact.</div>
      {tip.node}
    </div>
  );
}

export function BarList({ rows, format = (v: number) => num(v), max: maxIn, color = 'var(--series-1)' }: {
  rows: { label: string; value: number; hint?: string }[]; format?: (v: number) => string; max?: number; color?: string;
}) {
  const tip = useTooltip();
  const max = maxIn ?? Math.max(...rows.map(r => r.value), 1e-9);
  return (
    <div>
      {rows.map(r => (
        <div key={r.label} className="bar-row" {...tip.bind(<><b>{r.label}</b>: {format(r.value)}{r.hint ? <><br /><span className="muted">{r.hint}</span></> : null}</>)}>
          <span className="muted" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.label}</span>
          <div className="bar-track"><div className="bar-fill" style={{ width: `${Math.max((r.value / max) * 100, r.value > 0 ? 1.5 : 0)}%`, background: color }} /></div>
          <span className="tabular strong" style={{ textAlign: 'right' }}>{format(r.value)}</span>
        </div>
      ))}
      {tip.node}
    </div>
  );
}

/** Investigator-hours portfolio: effort (x) vs expected recovery (y), with the capacity budget line. */
export function PortfolioScatter({ cases, capacity, onPick }: { cases: QueueCase[]; capacity: number; onPick?: (id: string) => void }) {
  const tip = useTooltip();
  const [box, W] = useWidth<HTMLDivElement>();
  const H = 320, P = { l: 64, r: 18, t: 16, b: 40 };
  const xMax = Math.max(capacity * 1.1, ...cases.map(c => c.effort_hours)) * 1.05;
  const yMax = Math.max(...cases.map(c => c.expected_recovery), 1) * 1.15;
  const x = (v: number) => P.l + (v / xMax) * (W - P.l - P.r);
  const y = (v: number) => H - P.b - (v / yMax) * (H - P.t - P.b);
  const xticks = useMemo(() => { const step = xMax > 60 ? 20 : 10; return Array.from({ length: Math.floor(xMax / step) + 1 }, (_, i) => i * step); }, [xMax]);
  const yticks = [0, 0.25, 0.5, 0.75, 1].map(f => f * yMax);
  const color = (c: QueueCase) => (c.selected ? (c.exploration ? 'var(--series-2)' : 'var(--series-1)') : 'var(--mark-muted)');
  return (
    <div ref={box}>
      <div className="row" style={{ gap: 14, marginBottom: 6 }} aria-label="Legend">
        <span className="xs muted"><span className="legend-swatch" style={{ background: 'var(--series-1)', borderRadius: '50%' }} />Selected</span>
        <span className="xs muted"><span className="legend-swatch" style={{ background: 'var(--series-2)', borderRadius: '50%' }} />Exploration (10% reserve)</span>
        <span className="xs muted"><span className="legend-swatch" style={{ background: 'var(--mark-muted)', borderRadius: '50%' }} />Not selected</span>
        <span className="xs muted"><span className="legend-swatch" style={{ borderLeft: '2px dashed var(--bad)', width: 0, height: 12 }} />Capacity</span>
      </div>
      <svg width={W} height={H} role="img" aria-label="Expected recovery versus investigation effort" style={{ display: 'block' }}>
        {yticks.map(t => (
          <g key={t}>
            <line x1={P.l} x2={W - P.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
            <text x={P.l - 8} y={y(t) + 4} textAnchor="end" fontSize="11" fill="var(--text-3)">{inr(t)}</text>
          </g>
        ))}
        {xticks.map(t => <text key={t} x={x(t)} y={H - P.b + 16} textAnchor="middle" fontSize="11" fill="var(--text-3)">{t}h</text>)}
        <line x1={P.l} x2={W - P.r} y1={H - P.b} y2={H - P.b} stroke="var(--axis)" />
        <text x={(W + P.l) / 2} y={H - 4} textAnchor="middle" fontSize="11" fill="var(--text-2)">Investigation effort (hours)</text>
        <line x1={x(capacity)} x2={x(capacity)} y1={P.t} y2={H - P.b} stroke="var(--bad)" strokeWidth={1.5} strokeDasharray="5 4" />
        <text x={x(capacity) + 5} y={P.t + 11} fontSize="11" fill="var(--bad-text)" fontWeight={600}>Capacity {capacity}h</text>
        {cases.map(c => (
          <g key={c.case_id} style={{ cursor: onPick ? 'pointer' : 'default' }} onClick={() => onPick?.(c.case_id)}
            {...tip.bind(<><b>{c.case_id}</b> · rank #{c.rank}<br />{c.title}<br />Effort {c.effort_hours}h · Expected {inr(c.expected_recovery)}<br />Risk {c.risk} · {c.evidence_strength} evidence<br /><span className="muted">{c.selection_reason}</span></>)}>
            <circle cx={x(c.effort_hours)} cy={y(c.expected_recovery)} r={16} fill="transparent" />
            <motion.circle cx={x(c.effort_hours)} cy={y(c.expected_recovery)} r={5 + c.risk / 25} fill={color(c)} stroke="var(--chart-surface)" strokeWidth={2}
              initial={false} animate={{ cx: x(c.effort_hours), cy: y(c.expected_recovery) }} />
            {c.selected && <text x={x(c.effort_hours) + 10} y={y(c.expected_recovery) - 8} fontSize="10.5" fill="var(--text-2)">{c.case_id.replace('CASE-', '#')}</text>}
          </g>
        ))}
      </svg>
      <div className="xs faint">Dot size = risk. A high-risk dot can sit outside the plan when its evidence is weak or effort is high.</div>
      {tip.node}
    </div>
  );
}

export function Calibration({ bins }: { bins: { bin: string; predicted: number; observed: number; n: number }[] }) {
  const tip = useTooltip();
  const S = 220, P = 30;
  const s = (v: number) => P + v * (S - P - 8);
  const yy = (v: number) => S - P - v * (S - P - 8) + 8;
  return (
    <div>
      <svg viewBox={`0 0 ${S} ${S}`} width="100%" style={{ maxWidth: 280 }} role="img" aria-label="Forecast calibration">
        {[0, 0.5, 1].map(t => (
          <g key={t}>
            <line x1={s(0)} x2={s(1)} y1={yy(t)} y2={yy(t)} stroke="var(--grid)" />
            <text x={P - 6} y={yy(t) + 4} fontSize="10" textAnchor="end" fill="var(--text-3)">{t * 100}%</text>
            <text x={s(t)} y={S - P + 18} fontSize="10" textAnchor="middle" fill="var(--text-3)">{t * 100}%</text>
          </g>
        ))}
        <line x1={s(0)} y1={yy(0)} x2={s(1)} y2={yy(1)} stroke="var(--axis)" strokeDasharray="4 4" />
        {bins.map(b => (
          <g key={b.bin} {...tip.bind(<><b>Bin {b.bin}</b><br />Predicted {(b.predicted * 100).toFixed(0)}% · Observed {(b.observed * 100).toFixed(0)}%<br />n = {b.n}</>)}>
            <circle cx={s(b.predicted)} cy={yy(b.observed)} r={14} fill="transparent" />
            <circle cx={s(b.predicted)} cy={yy(b.observed)} r={5} fill="var(--series-1)" stroke="var(--chart-surface)" strokeWidth={2} />
          </g>
        ))}
      </svg>
      <div className="xs faint">x = predicted probability, y = observed rate. On the dashed line = well calibrated.</div>
      {tip.node}
    </div>
  );
}

export function Spark({ values, w = 140, h = 34 }: { values: number[]; w?: number; h?: number }) {
  if (values.length < 2) return null;
  const max = Math.max(...values, 1);
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * (w - 4) + 2},${h - 3 - (v / max) * (h - 8)}`).join(' ');
  return (
    <svg width={w} height={h} aria-hidden>
      <polyline points={pts} fill="none" stroke="var(--series-1)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

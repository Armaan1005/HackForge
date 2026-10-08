// Lightweight SVG/HTML charts in the Prism style: rounded 8px tracks, calm green fills.
// Dataviz rules kept: single series = one hue and no legend, 2+ series = legend + direct labels,
// text in ink colours, tooltip on every mark, real-pixel widths so text never scales.
import { motion } from 'motion/react';
import { useMemo } from 'react';
import { inr, num } from '../lib/format';
import { useWidth } from '../lib/hooks';
import type { QueueCase } from '../lib/types';
import { useTooltip } from './ui';

// Ordinal green ramp (validated: monotone, light end >= 2:1 on white).
const ORDINAL = ['#8cc3a8', '#62aa88', '#3f8f6b', '#2b7253', '#1d563d'];

export function Funnel({ stages }: { stages: { label: string; value: number; note?: string }[] }) {
  const tip = useTooltip();
  const max = Math.max(...stages.map(s => s.value), 1);
  return (
    <div role="list" aria-label="Alerts to cases">
      {stages.map((s, i) => {
        const w = Math.max((Math.log10(s.value + 1) / Math.log10(max + 1)) * 100, 3);
        return (
          <div key={s.label} className="funnel-step" role="listitem" {...tip.bind(<><b>{s.label}</b>: {num(s.value)}{s.note ? <><br /><span className="muted">{s.note}</span></> : null}</>)}>
            <span className="muted">{s.label}</span>
            <div className="track"><motion.div className="fill" style={{ background: ORDINAL[Math.min(i, ORDINAL.length - 1)] }} initial={{ width: 0 }} animate={{ width: `${w}%` }} transition={{ duration: 0.8, delay: i * 0.07, ease: [0.22, 1, 0.36, 1] }} /></div>
            <b className="tabular" style={{ textAlign: 'right' }}>{num(s.value)}</b>
          </div>
        );
      })}
      {tip.node}
    </div>
  );
}

/** Effort (x) vs expected recovery (y) with the capacity line. */
export function PortfolioScatter({ cases, capacity, onPick }: { cases: QueueCase[]; capacity: number; onPick?: (id: string) => void }) {
  const tip = useTooltip();
  const [box, W] = useWidth<HTMLDivElement>();
  const H = 300, P = { l: 64, r: 18, t: 16, b: 40 };
  const xMax = Math.max(capacity * 1.1, ...cases.map(c => c.effort_hours)) * 1.05;
  const yMax = Math.max(...cases.map(c => c.expected_recovery), 1) * 1.15;
  const x = (v: number) => P.l + (v / xMax) * (W - P.l - P.r);
  const y = (v: number) => H - P.b - (v / yMax) * (H - P.t - P.b);
  const xticks = useMemo(() => { const step = xMax > 60 ? 20 : 10; return Array.from({ length: Math.floor(xMax / step) + 1 }, (_, i) => i * step); }, [xMax]);
  const yticks = [0, 0.5, 1].map(f => f * yMax);
  const color = (c: QueueCase) => (c.selected ? (c.exploration ? 'var(--series-2)' : 'var(--series-1)') : 'var(--mark-muted)');
  return (
    <div ref={box}>
      <div className="row-flex xs muted" style={{ gap: 16, marginBottom: 4 }} aria-label="Legend">
        <span><span className="legend-swatch" style={{ background: 'var(--series-1)', borderRadius: '50%' }} />In today's plan</span>
        <span><span className="legend-swatch" style={{ background: 'var(--series-2)', borderRadius: '50%' }} />Exploration</span>
        <span><span className="legend-swatch" style={{ background: 'var(--mark-muted)', borderRadius: '50%' }} />Not picked</span>
      </div>
      <svg width={W} height={H} role="img" aria-label="Expected recovery versus effort" style={{ display: 'block' }}>
        {yticks.map(t => (
          <g key={t}>
            <line x1={P.l} x2={W - P.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
            <text x={P.l - 8} y={y(t) + 4} textAnchor="end" fontSize="11" fill="var(--text-3)">{inr(t)}</text>
          </g>
        ))}
        {xticks.map(t => <text key={t} x={x(t)} y={H - P.b + 18} textAnchor="middle" fontSize="11" fill="var(--text-3)">{t}h</text>)}
        <line x1={P.l} x2={W - P.r} y1={H - P.b} y2={H - P.b} stroke="var(--axis)" />
        <line x1={x(capacity)} x2={x(capacity)} y1={P.t} y2={H - P.b} stroke="var(--accent)" strokeWidth={1.5} strokeDasharray="5 5" />
        <text x={x(capacity) + 6} y={P.t + 11} fontSize="11" fill="var(--accent)" fontWeight={650}>Your capacity · {capacity}h</text>
        {cases.map(c => (
          <g key={c.case_id} style={{ cursor: onPick ? 'pointer' : 'default' }} onClick={() => onPick?.(c.case_id)}
            {...tip.bind(<><b>{c.title}</b><br />{c.effort_hours}h · {inr(c.expected_recovery)} expected · risk {c.risk}<br /><span className="muted">{c.selection_reason}</span></>)}>
            <circle cx={x(c.effort_hours)} cy={y(c.expected_recovery)} r={16} fill="transparent" />
            <circle cx={x(c.effort_hours)} cy={y(c.expected_recovery)} r={6 + c.risk / 22} fill={color(c)} stroke="var(--chart-surface)" strokeWidth={2} />
            {c.selected && <text x={x(c.effort_hours) + 12} y={y(c.expected_recovery) + 4} fontSize="11" fill="var(--text-2)">{c.case_id.replace('CASE-', '#')}</text>}
          </g>
        ))}
      </svg>
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
      <svg viewBox={`0 0 ${S} ${S}`} width="100%" style={{ maxWidth: 260 }} role="img" aria-label="Forecast calibration">
        {[0, 0.5, 1].map(t => (
          <g key={t}>
            <line x1={s(0)} x2={s(1)} y1={yy(t)} y2={yy(t)} stroke="var(--grid)" />
            <text x={P - 6} y={yy(t) + 4} fontSize="10" textAnchor="end" fill="var(--text-3)">{t * 100}%</text>
            <text x={s(t)} y={S - P + 18} fontSize="10" textAnchor="middle" fill="var(--text-3)">{t * 100}%</text>
          </g>
        ))}
        <line x1={s(0)} y1={yy(0)} x2={s(1)} y2={yy(1)} stroke="var(--axis)" strokeDasharray="4 4" />
        {bins.map(b => (
          <g key={b.bin} {...tip.bind(<><b>{b.bin}</b><br />Predicted {(b.predicted * 100).toFixed(0)}% · observed {(b.observed * 100).toFixed(0)}% · n = {b.n}</>)}>
            <circle cx={s(b.predicted)} cy={yy(b.observed)} r={14} fill="transparent" />
            <circle cx={s(b.predicted)} cy={yy(b.observed)} r={5.5} fill="var(--series-1)" stroke="var(--chart-surface)" strokeWidth={2} />
          </g>
        ))}
      </svg>
      <p className="xs faint">Predicted vs observed · on the dashed line is perfect</p>
      {tip.node}
    </div>
  );
}

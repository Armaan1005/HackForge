import { AlarmClock, Calculator, CheckCircle2, Compass, ListOrdered, Target } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PortfolioScatter } from '../components/charts';
import { Banner, Card, ErrorState, RiskRing, Segmented, Sheet, Skeleton, Stat, StatusPill, StrengthPill } from '../components/ui';
import { api, useEngineSource } from '../lib/api';
import { inr, PATTERN, pct, titleCase } from '../lib/format';
import { useAsync, useDebounced } from '../lib/hooks';
import type { Horizon } from '../lib/types';

export function QueuePage() {
  const nav = useNavigate();
  const source = useEngineSource();
  const [capacity, setCapacity] = useState(40);
  const [horizon, setHorizon] = useState<Horizon>(30);
  const [view, setView] = useState<'all' | 'plan' | 'out'>('all');
  const [formula, setFormula] = useState(false);
  const cap = useDebounced(capacity, 120);
  const q = useAsync(() => api.queue(cap, horizon), [cap, horizon]);

  if (q.error) return <ErrorState error={q.error} onRetry={q.reload} />;
  const d = q.data;
  const rows = d?.cases.filter(c => view === 'all' || (view === 'plan' ? c.selected : !c.selected)) ?? [];

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <div className="eyebrow">SIU queue · portfolio planner</div>
          <h1>Which {d?.selected_count ?? ''} investigations create the most value today?</h1>
          <p className="subtitle">Not sorted by risk score. Each case is an investment: expected recovery and avoided future loss, weighted by member harm, severity and evidence strength, against the hours it takes. Drag the capacity and the plan re-optimizes.</p>
        </div>
      </div>

      {source === 'fixture' && <Banner>Engine API not running yet: re-planning the contract fixture in your browser with the same formula. Live data appears automatically when Part A is up.</Banner>}

      <Card>
        <div className="grid-2" style={{ alignItems: 'center' }}>
          <div className="stack-sm">
            <div className="row between"><span className="strong">Investigator capacity today</span><span className="stat-value tabular" style={{ fontSize: '1.4rem', marginTop: 0 }}>{capacity} h</span></div>
            <input type="range" min={8} max={120} step={2} value={capacity} aria-label="Investigator capacity in hours"
              style={{ ['--pct' as string]: `${((capacity - 8) / 112) * 100}%` }} onChange={e => setCapacity(Number(e.target.value))} />
            <div className="row between xs faint"><span>8 h · one investigator, one day</span><span>120 h · full team, one week</span></div>
          </div>
          <div className="stack-sm" style={{ alignItems: 'flex-end' }}>
            <span className="small muted">Forecast horizon for repeat or escalating risk</span>
            <Segmented label="Horizon" value={horizon} onChange={setHorizon} options={[{ value: 30, label: '30 days' }, { value: 60, label: '60 days' }, { value: 90, label: '90 days' }]} />
            <button className="btn btn-ghost btn-sm" onClick={() => setFormula(true)}><Calculator size={14} />How priority is computed</button>
          </div>
        </div>
      </Card>

      <div className="grid-4">
        <Stat icon={CheckCircle2} label="Cases in plan" value={d ? d.selected_count : '…'} sub={d ? `of ${d.eligible_cases} eligible · ${d.total_cases} total` : ''} />
        <Stat icon={Target} label="Hours used" value={d ? `${d.hours_used} h` : '…'} sub={d ? `${d.exploration_hours_reserved} h reserved for exploration` : ''} />
        <Stat icon={ListOrdered} label="Expected recovery" value={d ? inr(d.expected_recovery_selected) : '…'} sub={`plus avoided loss over ${horizon} days`} />
        <Stat icon={Compass} label="Recovery per hour" value={d ? inr(d.recovery_per_hour) : '…'} sub="Higher than ranking by risk alone" />
      </div>

      <Card title="Effort vs expected recovery" icon={Target} action={<span className="xs faint">click a dot to open the case</span>}>
        {d ? <PortfolioScatter cases={d.cases} capacity={capacity} onPick={id => nav(`/cases/${id}`)} /> : <Skeleton h={300} />}
      </Card>

      <Card className="card-flush">
        <div className="row between" style={{ padding: '14px 16px' }}>
          <h3>Ranked cases</h3>
          <Segmented size="sm" label="Filter" value={view} onChange={setView} options={[{ value: 'all', label: 'All' }, { value: 'plan', label: 'In plan' }, { value: 'out', label: 'Not selected' }]} />
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead><tr>
              <th>#</th><th>Case</th><th>Status</th><th className="num">Risk</th><th className="num">Exposure</th><th className="num">Expected</th>
              <th className="num">Harm</th><th className="num">Sev.</th><th>Evidence</th><th className="num">Effort</th><th className="num">₹ / hour</th>
              <th className="num">{horizon}d risk</th><th>Clock</th><th>Why</th>
            </tr></thead>
            <tbody>
              {!d && <tr><td colSpan={14}><Skeleton h={180} /></td></tr>}
              {rows.map(c => (
                <tr key={c.case_id} className={`clickable ${c.selected ? '' : 'dim'}`} onClick={() => nav(`/cases/${c.case_id}`)}>
                  <td className="tabular strong">{c.rank}</td>
                  <td style={{ minWidth: 220 }}>
                    <div className="strong">{c.title}</div>
                    <div className="xs muted">{c.case_id} · {PATTERN[c.pattern] ?? titleCase(c.pattern)}{c.exploration ? ' · exploration' : ''}</div>
                  </td>
                  <td><StatusPill status={c.status} /></td>
                  <td className="num"><RiskRing value={c.risk} size={36} /></td>
                  <td className="num">{inr(c.dollars_at_risk)}</td>
                  <td className="num strong">{inr(c.expected_recovery)}</td>
                  <td className="num">{c.member_harm.toFixed(2)}</td>
                  <td className="num">{c.severity}</td>
                  <td><StrengthPill strength={c.evidence_strength} /></td>
                  <td className="num">{c.effort_hours} h</td>
                  <td className="num">{inr(c.recovery_per_hour)}</td>
                  <td className="num">{pct(c.horizon_risk[String(horizon)])}</td>
                  <td className="nowrap">{c.days_until_release == null ? <span className="faint">—</span> : <span className={`chip ${c.hold_recommended ? 'chip-warn' : ''}`}>{c.hold_recommended && <AlarmClock size={12} />}{c.days_until_release}d</span>}</td>
                  <td className="small muted" style={{ minWidth: 240 }}>{c.selection_reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Sheet open={formula} onClose={() => setFormula(false)} title="How priority is computed">
        <div className="stack small">
          <p className="muted">Prototype logic (not an industry standard), computed by the engine, never by the AI:</p>
          <pre className="mono" style={{ background: 'var(--surface)', padding: 14, borderRadius: 12, border: '1px solid var(--line)', whiteSpace: 'pre-wrap' }}>
{`value  = expected_recovery
       + horizon_risk[h] × projected_monthly_loss × (h / 30) × recovery_rate
value ×= (1 + member_harm) × (0.8 + 0.1 × severity) × strength_multiplier
         (strong 1.0 · moderate 0.75 · weak 0.4)
priority = value ÷ effort_hours

plan = maximize Σ value  subject to  Σ effort ≤ capacity × 90%
       + 10% of capacity for exploration cases`}
          </pre>
          <p className="muted">Cleared and monitor cases are not eligible. The exploration reserve picks cases unlike past confirmed fraud, so the system doesn't only find what it already knows. Expected recovery = exposure × confidence × recovery rate.</p>
        </div>
      </Sheet>
    </div>
  );
}

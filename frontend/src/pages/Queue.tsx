import { AlarmClock, Info } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PortfolioScatter } from '../components/charts';
import { Card, ErrorState, RiskRing, Segmented, Sheet, Skeleton, StatusPill, StrengthPill } from '../components/ui';
import { api } from '../lib/api';
import { inr } from '../lib/format';
import { useAsync, useDebounced } from '../lib/hooks';
import type { Horizon } from '../lib/types';

export function QueuePage() {
  const nav = useNavigate();
  const [capacity, setCapacity] = useState(40);
  const [horizon, setHorizon] = useState<Horizon>(30);
  const [view, setView] = useState<'plan' | 'all'>('all');
  const [formula, setFormula] = useState(false);
  const cap = useDebounced(capacity, 120);
  const q = useAsync(() => api.queue(cap, horizon), [cap, horizon]);
  if (q.error) return <ErrorState error={q.error} onRetry={q.reload} />;
  const d = q.data;
  const rows = d?.cases.filter(c => view === 'all' || c.selected) ?? [];

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <div className="eyebrow">Queue</div>
          <h1>Ranked by value per investigator hour</h1>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={() => setFormula(true)}><Info size={14} />How it's ranked</button>
      </div>

      <Card>
        <div className="strip" style={{ justifyContent: 'space-between' }}>
          <div style={{ flex: '1 1 320px', maxWidth: 460 }} className="stack-sm">
            <div className="row between"><span className="small strong">Capacity</span><span className="strong tabular">{capacity} h</span></div>
            <input type="range" min={8} max={120} step={2} value={capacity} aria-label="Investigator capacity in hours"
              style={{ ['--pct' as string]: `${((capacity - 8) / 112) * 100}%` }} onChange={e => setCapacity(Number(e.target.value))} />
          </div>
          <Segmented label="Horizon" value={horizon} onChange={setHorizon} options={[{ value: 30, label: '30d' }, { value: 60, label: '60d' }, { value: 90, label: '90d' }]} />
          <div className="metric"><div className="k">In plan</div><div className="v">{d?.selected_count ?? '…'}</div></div>
          <div className="metric"><div className="k">Hours used</div><div className="v">{d ? `${d.hours_used}h` : '…'}</div></div>
          <div className="metric"><div className="k">Expected recovery</div><div className="v">{d ? inr(d.expected_recovery_selected) : '…'}</div></div>
        </div>
      </Card>

      <Card title="Effort vs recovery">
        {d ? <PortfolioScatter cases={d.cases} capacity={capacity} onPick={id => nav(`/cases/${id}`)} /> : <Skeleton h={300} />}
      </Card>

      <Card className="card-flush" title="Cases" action={<Segmented size="sm" label="Filter" value={view} onChange={setView} options={[{ value: 'all', label: 'All' }, { value: 'plan', label: 'In plan' }]} />}>
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>#</th><th>Case</th><th>Status</th><th className="num">Risk</th><th>Evidence</th><th className="num">Effort</th><th className="num">Expected</th><th>Pay</th></tr></thead>
            <tbody>
              {!d && <tr><td colSpan={8}><Skeleton h={160} /></td></tr>}
              {rows.map(c => (
                <tr key={c.case_id} className={`clickable ${c.selected ? '' : 'dim'}`} onClick={() => nav(`/cases/${c.case_id}`)} title={c.selection_reason}>
                  <td className="tabular strong">{c.rank}</td>
                  <td style={{ minWidth: 260 }}>
                    <div className="strong">{c.title}</div>
                    <div className="xs muted">{c.selected ? (c.exploration ? 'Exploration pick' : c.case_id) : c.selection_reason}</div>
                  </td>
                  <td><StatusPill status={c.status} /></td>
                  <td className="num"><RiskRing value={c.risk} size={34} /></td>
                  <td><StrengthPill strength={c.evidence_strength} /></td>
                  <td className="num">{c.effort_hours}h</td>
                  <td className="num strong">{inr(c.expected_recovery)}</td>
                  <td className="nowrap">{c.days_until_release == null ? <span className="faint">—</span> : <span className={`chip ${c.hold_recommended ? 'chip-warn' : ''}`}>{c.hold_recommended && <AlarmClock size={12} />}{c.days_until_release}d</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Sheet open={formula} onClose={() => setFormula(false)} title="How it's ranked">
        <pre className="mono small" style={{ background: 'var(--surface)', padding: 14, borderRadius: 12, border: '1px solid var(--line)', whiteSpace: 'pre-wrap', margin: 0 }}>
{`value = expected recovery + avoided future loss (horizon)
      × (1 + member harm) × severity × evidence strength
priority = value ÷ effort hours

Plan fills 90% of capacity by value,
10% goes to exploration cases.`}
        </pre>
        <p className="small muted" style={{ marginTop: 12 }}>Computed by the engine, never by the AI. Cleared and monitor cases aren't eligible.</p>
      </Sheet>
    </div>
  );
}

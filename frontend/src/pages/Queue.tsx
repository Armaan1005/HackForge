import { motion } from 'motion/react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PortfolioChart } from '../components/PortfolioChart';
import { Icon } from '../components/Icon';
import { Card, ErrorState, PageHeader, RiskPill, Segmented, Sheet, Skeleton, Status, Strength } from '../components/ui';
import { api } from '../lib/api';
import { inr, PATTERN_ICON } from '../lib/format';
import { useAsync, useDebounced } from '../lib/hooks';
import { spring } from '../lib/theme';
import type { Horizon } from '../lib/types';

/** Hours as people, assuming an 8-hour working day: 16h -> "2 investigators × 8h". */
const staffing = (hours: number) => {
  const n = hours / 8;
  return Number.isInteger(n) ? `${n} investigator${n === 1 ? '' : 's'} × 8h` : `about ${n.toFixed(1)} investigators × 8h`;
};

export function QueuePage() {
  const nav = useNavigate();
  const [capacity, setCapacity] = useState(40);
  const [horizon, setHorizon] = useState<Horizon>(30);
  const [view, setView] = useState<'all' | 'plan'>('all');
  const [formula, setFormula] = useState(false);
  const cap = useDebounced(capacity, 120);
  const q = useAsync(() => api.queue(cap, horizon), [cap, horizon]);
  if (q.error) return <ErrorState error={q.error} onRetry={q.reload} />;
  const d = q.data;
  const rows = d?.cases.filter(c => view === 'all' || c.selected) ?? [];

  return (
    <>
      <PageHeader eyebrow="Cases" title="Where your hours go furthest"
        actions={<button className="btn btn-ghost btn-sm" onClick={() => setFormula(true)}><Icon name="hint" size={15} />How cases are ranked</button>} />

      <div className="stats" style={{ marginBottom: 20 }}>
        <div className="stat"><b>{d?.selected_count ?? '…'}</b><span>cases in today's plan</span></div>
        <div className="stat"><b>{d ? `${d.hours_used}h` : '…'}</b><span>of {capacity} hours used</span></div>
        <div className="stat"><b>{d ? inr(d.expected_recovery_selected) : '…'}</b><span>likely recovered</span></div>
        <div className="stat"><b>{d ? inr(d.recovery_per_hour) : '…'}</b><span>per hour</span></div>
      </div>

      <div className="grid-2" style={{ gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.6fr)', marginBottom: 20, alignItems: 'start' }}>
        <Card>
          <div className="slider-head"><b>Investigator hours today</b><span className="slider-val">{capacity}h</span></div>
          <p className="xs muted" style={{ margin: '-4px 0 8px' }}>{staffing(capacity)}</p>
          <input type="range" min={8} max={120} step={2} value={capacity} aria-label="Investigator hours"
            style={{ ['--pct' as string]: `${((capacity - 8) / 112) * 100}%` }} onChange={e => setCapacity(Number(e.target.value))} />
          <div className="row-flex xs faint" style={{ justifyContent: 'space-between', marginTop: 6 }}><span>8h · 1 investigator</span><span>120h · 15 investigators</span></div>
          <div className="divider" />
          <div className="row-flex" style={{ justifyContent: 'space-between' }}>
            <span className="small strong">Look ahead</span>
            <Segmented size="sm" label="Look ahead" value={horizon} onChange={setHorizon} options={[{ value: 30, label: '30 days' }, { value: 60, label: '60 days' }, { value: 90, label: '90 days' }]} />
          </div>
        </Card>
        <Card style={{ padding: 0 }}>
          {d ? <PortfolioChart cases={d.cases} capacity={capacity} onPick={id => nav(`/cases/${id}`)} /> : <Skeleton h={300} />}
        </Card>
      </div>

      <div style={{ marginBottom: 14 }}><Segmented size="sm" label="Show" value={view} onChange={setView} options={[{ value: 'all', label: 'All cases' }, { value: 'plan', label: "Today's plan" }]} /></div>
      <Card style={{ padding: 0 }}>
        {!d ? <Skeleton h={260} style={{ margin: 16 }} /> : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Case</th><th>Status</th><th>Risk</th><th>Evidence</th><th className="num">Effort</th><th className="num">Likely recovered</th><th>Payment</th></tr></thead>
              <tbody>
                {rows.map((c, i) => (
                  <motion.tr key={c.case_id} className={`clickable ${c.selected ? '' : 'dim'}`} onClick={() => nav(`/cases/${c.case_id}`)} tabIndex={0}
                    onKeyDown={e => e.key === 'Enter' && nav(`/cases/${c.case_id}`)} title={c.selection_reason}
                    initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ ...spring, delay: i * 0.04 }}>
                    <td>
                      <div className="row-nw">
                        <span className="row-icon"><Icon name={PATTERN_ICON[c.pattern] ?? 'inspect'} size={15} /></span>
                        <div style={{ minWidth: 0 }}>
                          <b>{c.title}</b>
                          <div className="small muted clamp-1" style={{ maxWidth: 420 }}>{c.selected ? (c.exploration ? 'Exploration pick: unlike past fraud' : `#${c.rank} in today's plan`) : c.selection_reason.replace(/^Not selected: /, '')}</div>
                        </div>
                      </div>
                    </td>
                    <td><Status value={c.status} /></td>
                    <td><RiskPill value={c.risk} /></td>
                    <td><Strength value={c.evidence_strength} /></td>
                    <td className="num">{c.effort_hours}h</td>
                    <td className="num"><b>{inr(c.expected_recovery)}</b></td>
                    <td className="nowrap">{c.days_until_release == null ? <span className="faint">—</span>
                      : c.hold_recommended ? <span className="review-pill review-pending"><Icon name="pending" size={11} />{c.days_until_release} day{c.days_until_release === 1 ? '' : 's'}</span>
                        : <span className="small muted">{c.days_until_release} day{c.days_until_release === 1 ? '' : 's'}</span>}</td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Sheet open={formula} onClose={() => setFormula(false)} title="How cases are ranked">
        <ul className="list-check">
          <li><Icon name="money-bills" size={14} /><span>Start with the money we're likely to recover, plus the loss avoided over the next {horizon} days.</span></li>
          <li><Icon name="employee" size={14} /><span>Weigh it up by how many members could be harmed and how serious the pattern is.</span></li>
          <li><Icon name="inspection" size={14} /><span>Weigh it down when the evidence is weak.</span></li>
          <li><Icon name="time-entry-request" size={14} /><span>Divide by the hours it takes, then fill your hours with the best cases.</span></li>
          <li><Icon name="lab" size={14} /><span>Keep 10% of time for cases unlike anything seen before.</span></li>
        </ul>
        <p className="small muted" style={{ marginTop: 16 }}>All of this is computed by code, not by the AI.</p>
      </Sheet>
    </>
  );
}

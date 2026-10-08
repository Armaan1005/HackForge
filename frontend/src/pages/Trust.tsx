import { BadgeCheck, ClipboardList, Gauge, Scale, ShieldCheck, Target, Users } from 'lucide-react';
import { useState } from 'react';
import { BarList, Calibration } from '../components/charts';
import { Card, ErrorState, Segmented, Skeleton, Stat, StatusPill } from '../components/ui';
import { ai, api, localDecisions } from '../lib/api';
import { inr, num, pct } from '../lib/format';
import { useAsync } from '../lib/hooks';

export function Trust() {
  const t = useAsync(() => api.trust(), []);
  const aiStats = useAsync(() => ai.trust().catch(() => null), []);
  const audit = useAsync(() => api.audit(30), []);
  const [h, setH] = useState<'30' | '60' | '90'>('30');

  if (t.error) return <ErrorState error={t.error} onRetry={t.reload} />;
  if (!t.data) return <div className="stack-lg"><Skeleton h={90} /><div className="grid-4">{[0, 1, 2, 3].map(i => <Skeleton key={i} h={110} />)}</div><Skeleton h={300} /></div>;
  const d = t.data;
  const o = d.detection.overall;
  const fc = (d.forecast as Record<string, { auc: number; brier: number; calibration: { bin: string; predicted: number; observed: number; n: number }[] }>)[h];
  const fair = d.fairness;
  const local = localDecisions();

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <div className="eyebrow">Trust panel · measured on synthetic ground truth (seed {d.seed})</div>
          <h1>Why you can believe these numbers.</h1>
          <p className="subtitle">Precision and recall on planted schemes, how honest look-alikes were treated, whether forecasts are calibrated, whether small or rural providers are penalized, and how many AI statements the verifier blocked.</p>
        </div>
      </div>

      <div className="grid-4">
        <Stat icon={Target} label="Precision · recall" value={`${pct(o.precision)} · ${pct(o.recall)}`} sub={`F1 ${o.f1.toFixed(2)} across planted schemes`} />
        <Stat icon={Gauge} label="Rupees caught" value={inr(o.inr_caught)} sub={`of ${inr(o.inr_planted)} planted (${pct(o.inr_caught / o.inr_planted)})`} />
        <Stat icon={Users} label="Honest decoys defended" value={`${d.decoys.correctly_defended} / ${d.decoys.total}`} tone={d.decoys.flagged_needs_review ? 'warn' : 'good'} sub={`${d.decoys.flagged_needs_review} sent to SIU review · ${d.exoneration.planted_fraud_wrongly_cleared} planted fraud wrongly cleared`} />
        <Stat icon={BadgeCheck} label="AI statements verified" value={aiStats.data ? num(aiStats.data.statements_checked) : '—'} tone="good"
          sub={aiStats.data ? `${aiStats.data.uncited_blocked} uncited + ${aiStats.data.numbers_blocked} invented numbers blocked` : 'Part B backend offline'} />
      </div>

      <div className="grid-main">
        <Card className="card-flush">
          <div style={{ padding: '14px 16px 6px' }}><h3>Detection on planted schemes</h3></div>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Scheme</th><th>Detected</th><th className="num">Claim recall</th><th className="num">Planted</th><th className="num">Caught</th><th>Case</th></tr></thead>
              <tbody>
                {d.detection.by_scheme.map(s => (
                  <tr key={s.scheme_id}>
                    <td><b>{s.scheme_id}</b> {s.name}</td>
                    <td>{s.detected ? <span className="chip chip-good">Yes</span> : <span className="chip chip-bad">No</span>}</td>
                    <td className="num">{pct(s.claim_recall)}</td>
                    <td className="num">{inr(s.inr_planted)}</td>
                    <td className="num strong">{inr(s.inr_caught)}</td>
                    <td className="mono xs">{s.case_ids.join(', ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card title="Forecast calibration" icon={Scale} action={<Segmented size="sm" label="Horizon" value={h} onChange={setH} options={[{ value: '30', label: '30d' }, { value: '60', label: '60d' }, { value: '90', label: '90d' }]} />}>
          <div className="row" style={{ marginBottom: 8 }}><span className="chip">AUC {fc.auc}</span><span className="chip">Brier {fc.brier}</span><span className="xs faint">time-based holdout</span></div>
          {fc.calibration.length ? <Calibration bins={fc.calibration} /> : <p className="small muted">Calibration bins arrive with the live engine.</p>}
        </Card>
      </div>

      <div className="grid-3">
        <Card title="Flag rate by region" icon={Users}><BarList rows={fair.by_region.map(r => ({ label: r.group, value: r.flag_rate, hint: `${r.providers} providers` }))} format={v => pct(v, 1)} /></Card>
        <Card title="Flag rate by provider size" icon={Users}><BarList rows={fair.by_size.map(r => ({ label: r.group, value: r.flag_rate, hint: `${r.providers} providers` }))} format={v => pct(v, 1)} /></Card>
        <Card title="Rural vs urban" icon={Users}>
          <BarList rows={fair.rural_vs_urban.map(r => ({ label: r.group, value: r.flag_rate, hint: `${r.providers} providers` }))} format={v => pct(v, 1)} />
          <div className="divider" />
          <div className="small">Max disparity ratio <b>{fair.max_disparity_ratio.toFixed(2)}×</b> <span className="muted">· rural and small providers are not flagged more often.</span></div>
        </Card>
      </div>

      <div className="grid-main">
        <Card className="card-flush">
          <div style={{ padding: '14px 16px 6px' }}><h3>Golden set</h3><p className="xs muted">Fixed fraud, decoy and ambiguous cases re-checked on every run.</p></div>
          <table className="table">
            <thead><tr><th>Case</th><th>Kind</th><th>Expected</th><th>Actual</th><th>Match</th></tr></thead>
            <tbody>{d.golden_set.map(g => (
              <tr key={g.case_id}><td className="mono">{g.case_id}</td><td>{g.kind}</td><td><StatusPill status={g.expected} /></td><td><StatusPill status={g.actual} /></td><td>{g.match ? <span className="chip chip-good">✓</span> : <span className="chip chip-bad">✗</span>}</td></tr>
            ))}</tbody>
          </table>
        </Card>
        <Card title="Responsible AI" icon={ShieldCheck}>
          <ul className="small" style={{ margin: 0, paddingLeft: 18, display: 'grid', gap: 6 }}>
            <li>Code computes every score, rank, status and rupee figure. Gemini only reads and words them.</li>
            <li>Every AI statement must cite existing evidence; invented numbers are blocked.</li>
            <li>Medical records and judge input are treated as untrusted: injected instructions are flagged, never followed.</li>
            <li>No automatic denial, hold or fraud finding. A human approves every action, and it is logged.</li>
            <li>Uncertain cases ask for documentation instead of escalating.</li>
            <li>Limitations: synthetic data; heuristic confidence; we built both the attacks and the detector, so stress tests are optimistic.</li>
          </ul>
        </Card>
      </div>

      <Card className="card-flush">
        <div style={{ padding: '14px 16px 6px' }} className="row between"><h3 className="row-nw" style={{ gap: 8 }}><ClipboardList size={16} />Audit log</h3><span className="xs faint">{num((audit.data?.total ?? 0) + local.length)} events</span></div>
        <div className="list">
          {local.map(l => (
            <div key={l.decision_id} className="list-row small"><span className="mono xs faint nowrap">{l.recorded_at.replace('T', ' ')}</span><span className="chip chip-accent">decision.{l.action}</span><span className="mono">{l.case_id}</span><span className="muted">{l.user}{l.note ? ` · ${l.note}` : ''}</span><span className="xs faint">(local)</span></div>
          ))}
          {audit.data?.items.map(a => (
            <div key={a.audit_id} className="list-row small"><span className="mono xs faint nowrap">{a.ts.replace('T', ' ')}</span><span className="chip">{a.event}</span><span className="mono">{a.case_id ?? '—'}</span><span className="muted">{a.actor}</span></div>
          ))}
        </div>
      </Card>
    </div>
  );
}

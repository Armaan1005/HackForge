import { useState } from 'react';
import { Calibration } from '../components/charts';
import { Icon } from '../components/Icon';
import { Bar, Card, ErrorState, PageHeader, Section, Segmented, Skeleton, Status } from '../components/ui';
import { ai, api, localDecisions } from '../lib/api';
import { inr, num, pct } from '../lib/format';
import { useAsync } from '../lib/hooks';

export function Trust() {
  const t = useAsync(() => api.trust(), []);
  const aiStats = useAsync(() => ai.trust().catch(() => null), []);
  const audit = useAsync(() => api.audit(6), []);
  const [h, setH] = useState<'30' | '60' | '90'>('30');
  if (t.error) return <ErrorState error={t.error} onRetry={t.reload} />;
  if (!t.data) return <Skeleton h={400} />;
  const d = t.data, o = d.detection.overall, fair = d.fairness;
  const fc = (d.forecast as Record<string, { auc: number; brier: number; calibration: { bin: string; predicted: number; observed: number; n: number }[] }>)[h];
  const local = localDecisions();
  const maxFlag = Math.max(...[...fair.by_region, ...fair.by_size, ...fair.rural_vs_urban].map(r => r.flag_rate));

  return (
    <>
      <PageHeader eyebrow="How well it works" title="Can you trust these numbers?" subtitle="Measured on synthetic data where we planted fraud and honest look-alikes, so we know the right answers." />

      <div className="stats" style={{ marginBottom: 20 }}>
        <div className="stat"><b>{pct(o.recall)}</b><span>of planted fraud found</span></div>
        <div className="stat"><b>{pct(o.precision)}</b><span>of flagged cases were real</span></div>
        <div className="stat"><b>{d.decoys.correctly_defended} of {d.decoys.total}</b><span>honest look-alikes left alone</span></div>
        <div className="stat"><b>{aiStats.data ? num(aiStats.data.uncited_blocked + aiStats.data.numbers_blocked) : '—'}</b><span>AI statements blocked for missing evidence</span></div>
      </div>

      <div className="home-grid" style={{ marginBottom: 20 }}>
        <Card style={{ padding: 0 }}>
          <div className="pad"><h2>Planted schemes</h2></div>
          <table className="table">
            <thead><tr><th>Scheme</th><th>Found</th><th className="num">Claims caught</th><th className="num">Money caught</th></tr></thead>
            <tbody>
              {d.detection.by_scheme.map(s => (
                <tr key={s.scheme_id}>
                  <td><b>{s.name}</b></td>
                  <td>{s.detected ? <span className="review-pill review-done"><Icon name="accept" size={11} />Found</span> : <span className="review-pill review-pending">Missed</span>}</td>
                  <td className="num">{pct(s.claim_recall)}</td>
                  <td className="num" title={`of ${inr(s.inr_planted)}`}><b>{inr(s.inr_caught)}</b></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <div className="stack-lg panel-stack">
          <Card>
            <div className="row-flex" style={{ marginBottom: 10 }}><h2>Is the forecast honest?</h2><span className="spacer" />
              <Segmented size="sm" label="Look ahead" value={h} onChange={setH} options={[{ value: '30', label: '30d' }, { value: '60', label: '60d' }, { value: '90', label: '90d' }]} /></div>
            {fc.calibration.length ? <Calibration bins={fc.calibration} /> : <p className="small muted">Arrives with the live engine.</p>}
            <p className="small muted" style={{ marginTop: 6 }}>Ranking quality (AUC) {fc.auc}</p>
          </Card>
          <Card>
            <h2 style={{ marginBottom: 14 }}>Is anyone treated unfairly?</h2>
            <div className="stack">
              {[...fair.rural_vs_urban, ...fair.by_size].map(r => <Bar key={r.group} label={r.group.replace(/^Q\d /, '')} value={r.flag_rate} max={maxFlag * 1.2} right={pct(r.flag_rate, 1)} />)}
            </div>
            <p className="small muted" style={{ marginTop: 12 }}>Rural and small providers aren't flagged more often.</p>
          </Card>
        </div>
      </div>

      <div className="home-grid">
        <Section title="Golden set: checked on every run">
          {d.golden_set.map(g => (
            <div key={g.case_id} className="row">
              <span className="row-icon"><Icon name={g.match ? 'accept' : 'alert'} size={14} /></span>
              <div className="row-text"><span className="row-label">{g.case_id}</span><span className="row-desc">{g.kind} case</span></div>
              <Status value={g.actual} />
            </div>
          ))}
        </Section>
        <Section title="Audit trail">
          {local.map(l => (
            <div key={l.decision_id} className="row">
              <span className="row-icon"><Icon name="employee" size={14} /></span>
              <div className="row-text"><span className="row-label">{l.user} · {l.action.replace(/_/g, ' ')}</span><span className="row-desc">{l.case_id} · {l.recorded_at.replace('T', ' ')}{l.note ? ` · “${l.note}”` : ''}</span></div>
            </div>
          ))}
          {audit.data?.items.map(a => (
            <div key={a.audit_id} className="row">
              <span className="row-icon"><Icon name={a.actor === 'system' ? 'process' : 'employee'} size={14} /></span>
              <div className="row-text"><span className="row-label">{a.actor} · {a.event.replace(/[._]/g, ' ')}</span><span className="row-desc">{a.case_id ?? 'system'} · {a.ts.replace('T', ' ')}</span></div>
            </div>
          ))}
        </Section>
      </div>
    </>
  );
}

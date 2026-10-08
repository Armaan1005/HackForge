import { ArrowLeft, Bot, FileSearch, FileText, Gavel, HeartPulse, ListChecks, Network, Radar, Timer, UserCheck, Waypoints } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { BarList } from '../components/charts';
import { Banner, Card, ErrorState, RiskRing, Segmented, Skeleton, StatusPill, StrengthPill } from '../components/ui';
import { api } from '../lib/api';
import { inr, METHOD_LABEL, PATTERN, pct, relDays, titleCase } from '../lib/format';
import { useAsync } from '../lib/hooks';
import type { Horizon } from '../lib/types';
import { AskTab } from './case/AskTab';
import { BriefTab } from './case/BriefTab';
import { CourtTab } from './case/CourtTab';
import { DecisionBar } from './case/DecisionBar';
import { DocumentsTab } from './case/DocumentsTab';
import { EvidenceTab } from './case/EvidenceTab';
import { NetworkTab } from './case/NetworkTab';
import { TimelineTab } from './case/TimelineTab';

type Tab = 'evidence' | 'network' | 'timeline' | 'documents' | 'court' | 'brief' | 'ask';

export function CaseView() {
  const { id = '' } = useParams();
  const c = useAsync(() => api.case(id), [id]);
  const [tab, setTab] = useState<Tab>('evidence');
  const [horizon, setHorizon] = useState<Horizon>(30);
  const [highlight, setHighlight] = useState<string | null>(null);
  const fc = useAsync(() => (c.data ? api.forecast(c.data.primary_entity.entity_id, horizon) : Promise.resolve(null)), [c.data?.primary_entity.entity_id, horizon]);

  if (c.error) return <div className="stack"><Link to="/queue" className="row small"><ArrowLeft size={15} />Queue</Link><ErrorState error={c.error} onRetry={c.reload} /></div>;
  if (!c.data) return <div className="stack-lg"><Skeleton h={90} /><div className="grid-3"><Skeleton h={220} /><Skeleton h={220} /><Skeleton h={220} /></div><Skeleton h={400} /></div>;
  const k = c.data;
  const showOnGraph = (evId: string) => { setHighlight(evId); setTab('network'); };

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div style={{ minWidth: 0 }}>
          <Link to="/queue" className="row small no-print" style={{ marginBottom: 10, gap: 4 }}><ArrowLeft size={15} />SIU queue</Link>
          <div className="eyebrow">{k.case_id} · {PATTERN[k.pattern] ?? titleCase(k.pattern)}</div>
          <h1>{k.title}</h1>
          <div className="row" style={{ marginTop: 12 }}>
            <StatusPill status={k.verdict.status} />
            <StrengthPill strength={k.evidence_strength} />
            <span className="chip">Confidence {pct(k.confidence)}</span>
            <span className="chip">{k.scores.methods_agreeing} of 4 methods agree</span>
            {k.scores.hard_signal && <span className="chip chip-bad">Hard signal</span>}
            <span className="chip chip-accent"><UserCheck size={12} />Human approval required</span>
          </div>
        </div>
      </div>

      {k.fixture_sample && <Banner tone="warn">Fixture mode: this case's header comes from the queue, but its evidence is the sample case CASE-0001 until the engine API is running.</Banner>}

      <div className="grid-3">
        <Card title="Risk" icon={Radar}>
          <div className="row-nw" style={{ gap: 16, alignItems: 'center' }}>
            <RiskRing value={k.scores.risk} size={84} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <BarList rows={Object.entries(k.scores.by_method).map(([m, v]) => ({ label: METHOD_LABEL[m] ?? m, value: v, hint: k.layers[m] === 'ok' ? 'Layer running' : 'Layer unavailable' }))} format={v => v.toFixed(2)} max={1} />
            </div>
          </div>
          <div className="divider" />
          <div className="row between">
            <span className="small muted">Repeat or escalating FWA</span>
            <Segmented size="sm" label="Horizon" value={horizon} onChange={setHorizon} options={[{ value: 30, label: '30d' }, { value: 60, label: '60d' }, { value: 90, label: '90d' }]} />
          </div>
          <div className="row" style={{ marginTop: 10, alignItems: 'baseline' }}>
            <span className="stat-value" style={{ marginTop: 0 }}>{pct(k.horizon_risk[String(horizon)])}</span>
            <span className="xs faint">likelihood within {horizon} days</span>
          </div>
          {fc.data && (
            <div className="stack-sm" style={{ marginTop: 8 }}>
              {fc.data.top_drivers.map(dr => (
                <div key={dr.feature} className="xs muted">• {dr.label}: <b style={{ color: 'var(--text)' }}>{dr.value}</b> vs peer {dr.peer_median}</div>
              ))}
              <div className="xs faint">Model AUC {fc.data.model.auc_holdout} on a time-based holdout.</div>
            </div>
          )}
        </Card>

        <Card title="Money clock" icon={Timer}>
          <div className="kv">
            <dt>Exposure</dt><dd>{inr(k.money.dollars_at_risk)}</dd>
            <dt>Already paid</dt><dd>{inr(k.money.paid)}</dd>
            <dt>Pending</dt><dd>{inr(k.money.pending)} · {k.payment_clock.pending_claims} claims</dd>
            <dt>Expected recovery</dt><dd>{inr(k.money.expected_recovery)}</dd>
            <dt>Effort</dt><dd>{k.effort_hours} h · dead-end risk {pct(k.dead_end_risk)}</dd>
          </div>
          <div className="divider" />
          <div className="row-nw" style={{ gap: 12 }}>
            <div className="stat-value" style={{ marginTop: 0, color: (k.payment_clock.days_until_release ?? 99) <= 3 ? 'var(--bad-text)' : undefined }}>{k.payment_clock.days_until_release ?? '—'}</div>
            <div className="small"><b>{relDays(k.payment_clock.days_until_release)}</b><div className="xs muted">{k.payment_clock.next_release_date ?? ''}</div></div>
          </div>
          {k.payment_clock.hold_recommended && <div style={{ marginTop: 10 }}><Banner tone="warn">Hold recommended: {k.payment_clock.hold_reason}. This is a recommendation only.</Banner></div>}
        </Card>

        <Card title="Member impact" icon={HeartPulse}>
          <div className="row" style={{ alignItems: 'baseline' }}>
            <span className="stat-value" style={{ marginTop: 0 }}>{k.member_harm.members_affected}</span><span className="small muted">members affected</span>
          </div>
          <div className="kv" style={{ marginTop: 10 }}>
            <dt>Harm score</dt><dd>{k.member_harm.score.toFixed(2)}</dd>
            <dt>Vulnerable</dt><dd>{pct(k.member_harm.vulnerable_share)} (65+ or behavioral health)</dd>
            <dt>Clinical risk</dt><dd>{k.member_harm.clinical_risk.toFixed(2)}</dd>
            <dt>Severity</dt><dd>{k.severity} of 5</dd>
          </div>
          <div className="stack-sm" style={{ marginTop: 10 }}>
            {k.member_harm.drivers.map(d => <span key={d} className="xs muted">• {d}</span>)}
          </div>
        </Card>
      </div>

      <DecisionBar k={k} />

      <div className="row between no-print">
        <Segmented label="Case sections" value={tab} onChange={setTab} options={[
          { value: 'evidence', label: 'Evidence', icon: ListChecks },
          { value: 'network', label: 'Network', icon: Network },
          { value: 'timeline', label: 'Timeline', icon: Waypoints },
          { value: 'documents', label: 'Documents', icon: FileSearch },
          { value: 'court', label: 'Evidence Court', icon: Gavel },
          { value: 'brief', label: 'Brief', icon: FileText },
          { value: 'ask', label: 'Ask', icon: Bot },
        ]} />
      </div>

      {tab === 'evidence' && <EvidenceTab k={k} onShowOnGraph={showOnGraph} />}
      {tab === 'network' && <NetworkTab k={k} highlight={highlight} onClearHighlight={() => setHighlight(null)} />}
      {tab === 'timeline' && <TimelineTab k={k} />}
      {tab === 'documents' && <DocumentsTab k={k} />}
      {tab === 'court' && <CourtTab k={k} />}
      {tab === 'brief' && <BriefTab k={k} />}
      {tab === 'ask' && <AskTab k={k} />}
    </div>
  );
}

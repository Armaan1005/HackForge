import { AlarmClock, ArrowLeft } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Card, ErrorState, RiskRing, Segmented, Skeleton, StatusPill, StrengthPill } from '../components/ui';
import { api } from '../lib/api';
import { inr, PATTERN, pct, titleCase } from '../lib/format';
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

  if (c.error) return <div className="stack"><Link to="/queue" className="row small"><ArrowLeft size={15} />Queue</Link><ErrorState error={c.error} onRetry={c.reload} /></div>;
  if (!c.data) return <div className="stack-lg"><Skeleton h={80} /><Skeleton h={110} /><Skeleton h={400} /></div>;
  const k = c.data;
  const days = k.payment_clock.days_until_release;

  return (
    <div className="stack-lg">
      <div>
        <Link to="/queue" className="row small no-print" style={{ marginBottom: 10, gap: 4 }}><ArrowLeft size={15} />Queue</Link>
        <div className="eyebrow">{k.case_id} · {PATTERN[k.pattern] ?? titleCase(k.pattern)}{k.fixture_sample ? ' · sample evidence' : ''}</div>
        <h1>{k.title}</h1>
        <div className="row" style={{ marginTop: 10 }}>
          <StatusPill status={k.verdict.status} />
          <StrengthPill strength={k.evidence_strength} />
          <span className="chip">Confidence {pct(k.confidence)}</span>
        </div>
      </div>

      <Card>
        <div className="strip">
          <RiskRing value={k.scores.risk} size={64} />
          <div className="metric"><div className="k">Exposure</div><div className="v">{inr(k.money.dollars_at_risk)}</div><div className="s">{inr(k.money.pending)} pending</div></div>
          <div className="metric"><div className="k">Payment</div><div className="v" style={{ color: days != null && days <= 3 ? 'var(--bad-text)' : undefined }}>{days == null ? '—' : `${days} days`}</div>
            <div className="s">{k.payment_clock.hold_recommended ? <span style={{ color: 'var(--warn-text)' }}><AlarmClock size={11} style={{ verticalAlign: -1 }} /> hold suggested</span> : 'until release'}</div></div>
          <div className="metric"><div className="k">Members</div><div className="v">{k.member_harm.members_affected}</div><div className="s">{pct(k.member_harm.vulnerable_share)} vulnerable</div></div>
          <div className="metric"><div className="k">Repeat risk</div><div className="v">{pct(k.horizon_risk[String(horizon)])}</div>
            <Segmented size="sm" label="Horizon" value={horizon} onChange={setHorizon} options={[{ value: 30, label: '30d' }, { value: 60, label: '60d' }, { value: 90, label: '90d' }]} /></div>
          <div className="metric"><div className="k">Effort</div><div className="v">{k.effort_hours}h</div><div className="s">recover ~{inr(k.money.expected_recovery)}</div></div>
        </div>
      </Card>

      <DecisionBar k={k} />

      <div className="no-print">
        <Segmented label="Case sections" value={tab} onChange={setTab} options={[
          { value: 'evidence', label: 'Evidence' },
          { value: 'network', label: 'Network' },
          { value: 'timeline', label: 'Timeline' },
          { value: 'documents', label: 'Documents' },
          { value: 'court', label: 'Evidence Court' },
          { value: 'brief', label: 'Brief' },
          { value: 'ask', label: 'Ask' },
        ]} />
      </div>

      {tab === 'evidence' && <EvidenceTab k={k} onShowOnGraph={ev => { setHighlight(ev); setTab('network'); }} />}
      {tab === 'network' && <NetworkTab k={k} highlight={highlight} onClearHighlight={() => setHighlight(null)} />}
      {tab === 'timeline' && <TimelineTab k={k} />}
      {tab === 'documents' && <DocumentsTab k={k} />}
      {tab === 'court' && <CourtTab k={k} />}
      {tab === 'brief' && <BriefTab k={k} />}
      {tab === 'ask' && <AskTab k={k} />}
    </div>
  );
}

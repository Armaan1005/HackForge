import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Button, Card, ErrorState, PageHeader, Ring, Segmented, Skeleton, Status, Strength } from '../components/ui';
import { api } from '../lib/api';
import { inr, PATTERN, pct, titleCase } from '../lib/format';
import { useAsync } from '../lib/hooks';
import type { Horizon } from '../lib/types';
import { AskTab } from './case/AskTab';
import { BriefTab } from './case/BriefTab';
import { CourtTab } from './case/CourtTab';
import { DecisionBox } from './case/DecisionBar';
import { DocumentsTab } from './case/DocumentsTab';
import { EvidenceTab } from './case/EvidenceTab';
import { NetworkTab } from './case/NetworkTab';
import { TimelineTab } from './case/TimelineTab';

type Tab = 'evidence' | 'court' | 'network' | 'documents' | 'timeline' | 'brief' | 'ask';

export function CaseView() {
  const { id = '' } = useParams();
  const nav = useNavigate();
  const c = useAsync(() => api.case(id), [id]);
  const [params] = useSearchParams();
  const [tab, setTab] = useState<Tab>((params.get('tab') as Tab) || 'evidence');
  useEffect(() => { const t = params.get('tab') as Tab | null; if (t) setTab(t); }, [params]);
  const [horizon, setHorizon] = useState<Horizon>(30);
  const [highlight, setHighlight] = useState<string | null>(null);

  if (c.error) return <ErrorState error={c.error} onRetry={c.reload} />;
  if (!c.data) return <div className="stack-lg"><Skeleton h={70} /><div className="cand-top"><Skeleton h={300} /><Skeleton h={300} /></div></div>;
  const k = c.data;
  // The engine emits one evidence item per provider, so the summary dedupes by name.
  const uniq = (xs: string[]) => [...new Set(xs)];
  const forReview = uniq([...k.evidence].filter(e => e.direction === 'incriminating').sort((a, b) => b.severity - a.severity).map(e => e.name)).slice(0, 3);
  const legit = uniq([...k.evidence.filter(e => e.direction !== 'incriminating').map(e => e.name), ...k.peer_context.filter(p => p.direction !== 'incriminating').map(p => p.note ?? p.metric)]).slice(0, 3);
  const days = k.payment_clock.days_until_release;

  return (
    <>
      <Button variant="ghost" size="sm" icon="navigation-left-arrow" onClick={() => nav('/queue')} className="no-print">All cases</Button>
      <div style={{ height: 12 }} />
      <PageHeader eyebrow={`${PATTERN[k.pattern] ?? titleCase(k.pattern)} · ${k.case_id}${k.fixture_sample ? ' · sample evidence' : ''}`} title={k.title}
        actions={<><Strength value={k.evidence_strength} /><Status value={k.verdict.status} /><Button size="sm" variant="tinted" icon="decision" onClick={() => setTab('court')}>Hear it in court</Button></>} />

      <div className="cand-top" style={{ marginBottom: 20 }}>
        <Card className="card-accent">
          <div className="rec-head">
            <Ring value={k.scores.risk} size={88} label={`Risk ${k.scores.risk} of 100`}>
              <div style={{ textAlign: 'center', lineHeight: 1.1 }}><div style={{ fontSize: '1.5rem' }}>{k.scores.risk}</div><div style={{ fontSize: '.62rem', color: 'var(--text-3)', fontWeight: 650 }}>RISK</div></div>
            </Ring>
            <div style={{ flex: 1, minWidth: 260 }}>
              <p className="eyebrow" style={{ marginBottom: 4 }}>What Axon found</p>
              <p style={{ fontSize: '1.05rem', fontWeight: 550 }}>{k.verdict.next_action_text}.</p>
              <p className="small muted" style={{ marginTop: 4 }}>{pct(k.confidence)} confident · {k.scores.methods_agreeing} of 4 detection methods agree</p>
            </div>
          </div>
          <div className="wtw">
            <div className="wtw-col"><h4>Points to review</h4><ul>{forReview.map(t => <li key={t}>{t}</li>)}</ul></div>
            <div className="wtw-col"><h4>Could be legitimate</h4><ul>{legit.map(t => <li key={t}>{t}</li>)}</ul></div>
            <div className="wtw-col"><h4>Missing before deciding</h4><ul>{k.missing_documents.length ? k.missing_documents.map(m => <li key={m.doc_type}>{titleCase(m.doc_type)} for {m.claim_count} claims</li>) : <li>Nothing</li>}</ul></div>
          </div>
        </Card>

        <div className="stack-lg">
          <DecisionBox k={k} />
          <Card>
            <dl className="facts">
              <div><dt>At stake</dt><dd><b>{inr(k.money.dollars_at_risk)}</b> <span className="muted small">· {inr(k.money.pending)} not paid yet</span></dd></div>
              <div><dt>Payment</dt><dd style={{ color: days != null && days <= 3 ? 'var(--bad)' : undefined }}>{days == null ? 'Nothing pending' : `Releases in ${days} days`}</dd></div>
              <div><dt>Members</dt><dd>{k.member_harm.members_affected} affected · {pct(k.member_harm.vulnerable_share)} vulnerable</dd></div>
              <div><dt>Repeat risk</dt><dd className="row-flex" style={{ gap: 8 }}><b>{pct(k.horizon_risk[String(horizon)])}</b>
                <Segmented size="sm" label="Horizon" value={horizon} onChange={setHorizon} options={[{ value: 30, label: '30d' }, { value: 60, label: '60d' }, { value: 90, label: '90d' }]} /></dd></div>
              <div><dt>Effort</dt><dd>{k.effort_hours} hours</dd></div>
            </dl>
          </Card>
        </div>
      </div>

      <div className="no-print" style={{ marginBottom: 18, overflowX: 'auto' }}>
        <Segmented label="Case sections" value={tab} onChange={setTab} options={[
          { value: 'evidence', label: 'Evidence', icon: 'inspection' },
          { value: 'court', label: 'Evidence Court', icon: 'decision' },
          { value: 'network', label: 'Network', icon: 'org-chart' },
          { value: 'documents', label: 'Records', icon: 'documents' },
          { value: 'timeline', label: 'Timeline', icon: 'history' },
          { value: 'brief', label: 'Brief', icon: 'document-text' },
          { value: 'ask', label: 'Ask', icon: 'ai' },
        ]} />
      </div>

      {tab === 'evidence' && <EvidenceTab k={k} onShowOnGraph={ev => { setHighlight(ev); setTab('network'); }} />}
      {tab === 'court' && <CourtTab k={k} />}
      {tab === 'network' && <NetworkTab k={k} highlight={highlight} onClearHighlight={() => setHighlight(null)} />}
      {tab === 'documents' && <DocumentsTab k={k} />}
      {tab === 'timeline' && <TimelineTab k={k} />}
      {tab === 'brief' && <BriefTab k={k} />}
      {tab === 'ask' && <AskTab k={k} />}
    </>
  );
}

import { motion } from 'motion/react';
import { useState } from 'react';
import { Icon, type IconName } from '../../components/Icon';
import { Button, Card, Cite, ErrorState, Ring, Skeleton, Status } from '../../components/ui';
import { ai } from '../../lib/api';
import { useAsync } from '../../lib/hooks';
import type { Argument, CaseDetail, Court } from '../../lib/types';

function Side({ title, icon, tone, args, idx, extra }: { title: string; icon: IconName; tone: 'bad' | 'accent'; args: Argument[]; idx: Map<string, string>; extra?: React.ReactNode }) {
  return (
    <Card>
      <div className="card-title"><span className={`row-icon ${tone === 'bad' ? 'bad' : ''}`}><Icon name={icon} size={15} /></span><h2>{title}</h2></div>
      {args.map((a, i) => (
        <motion.div key={i} className="court-arg" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.06 * i }}>
          {a.point}{a.evidence_ids.map(id => <Cite key={id} id={id} title={idx.get(id)} />)}
        </motion.div>
      ))}
      {extra}
    </Card>
  );
}

function Steps({ c }: { c: Court }) {
  const steps: { icon: IconName; who: string; what: string; detail?: string }[] = [
    { icon: 'inspect', who: 'Prosecutor', what: `${c.prosecution.arguments.length} points for review`, detail: c.prosecution.source === 'llm' ? 'Gemini' : 'Template' },
    { icon: 'shield', who: 'Defense', what: `${c.defense.arguments.length} legitimate explanations`, detail: c.defense.source === 'llm' ? 'Gemini' : 'Template' },
    { icon: 'complete', who: 'Citation check', what: `${c.verifier.kept} statements kept, ${c.verifier.dropped} removed`, detail: c.verifier.dropped_items.map(d => `Removed: "${d.point}" (${d.reason})`).join(' · ') || 'Every number matched the evidence.' },
    { icon: 'decision', who: 'Verdict clerk', what: 'Put the code-computed status into words', detail: c.verdict.source === 'llm' ? 'Gemini' : 'Template' },
    { icon: 'employee', who: 'You', what: 'Make the decision' },
  ];
  return (
    <div className="trace">
      {steps.map((s, i) => (
        <div key={s.who} className={`trace-step ${i < 4 ? 'done' : 'running'}`}>
          <span className="trace-node"><Icon name={s.icon} size={18} /></span>
          <div><div className="trace-head"><span className="trace-agent">{s.who}</span><span className="small muted">{s.what}</span></div>{s.detail && <p className="trace-detail">{s.detail}</p>}</div>
        </div>
      ))}
    </div>
  );
}

export function CourtTab({ k }: { k: CaseDetail }) {
  const [refresh, setRefresh] = useState(0);
  const [showSteps, setShowSteps] = useState(false);
  const court = useAsync(() => ai.court(k.case_id, refresh > 0), [k.case_id, refresh]);
  const idx = new Map([...k.evidence.map(e => [e.evidence_id, e.name] as const), ...k.peer_context.map(p => [p.evidence_id, p.metric] as const)]);

  if (court.error) return <ErrorState error={new Error(`Couldn't reach the AI service (${court.error.message}).`)} onRetry={court.reload} />;
  if (!court.data) return <div className="court"><Skeleton h={300} /><Skeleton h={300} /></div>;
  const c = court.data, v = c.verdict;

  return (
    <div className="stack-lg">
      <div className="court">
        <Side title="Why it needs review" icon="inspect" tone="bad" args={c.prosecution.arguments} idx={idx} />
        <Side title="Why it might be fine" icon="shield" tone="accent" args={c.defense.arguments} idx={idx}
          extra={c.defense.missing_evidence.length > 0 && <div className="help-panel" style={{ marginTop: 12 }}><h4>Missing before deciding</h4>{c.defense.missing_evidence.map(m => <p key={m} className="small">{m}</p>)}</div>} />
      </div>

      <Card className="card-accent">
        <div className="rec-head">
          <Ring value={v.confidence * 100} size={76} label={`Confidence ${Math.round(v.confidence * 100)} percent`}>
            <div style={{ textAlign: 'center', lineHeight: 1.1 }}><div>{Math.round(v.confidence * 100)}%</div><div style={{ fontSize: '.6rem', color: 'var(--text-3)', fontWeight: 650 }}>SURE</div></div>
          </Ring>
          <div style={{ flex: 1, minWidth: 260 }}>
            <div className="row-flex" style={{ marginBottom: 6 }}><Status value={v.status} /><span className="small muted">· human approval required</span></div>
            <p>{v.summary}</p>
          </div>
        </div>
        <div className="divider" />
        <div className="row-flex">
          <span className="small muted"><Icon name="complete" size={13} className="inline" /> {c.verifier.kept} statements checked against the evidence{c.verifier.dropped ? `, ${c.verifier.dropped} removed` : ''}</span>
          <span className="spacer" />
          <Button variant="ghost" size="sm" icon={showSteps ? 'less' : 'add'} onClick={() => setShowSteps(s => !s)}>{showSteps ? 'Hide' : 'Show'} how this was made</Button>
          <Button variant="ghost" size="sm" icon="refresh" loading={court.loading} onClick={() => setRefresh(r => r + 1)}>Run again</Button>
        </div>
        {showSteps && <div style={{ marginTop: 16 }}><Steps c={c} /></div>}
      </Card>
    </div>
  );
}

import { motion } from 'motion/react';
import { BadgeCheck, RefreshCw, Scale, ShieldQuestion, Swords, UserCheck } from 'lucide-react';
import { useState } from 'react';
import { Button, Cite, ErrorState, Skeleton, SourceBadge, StatusPill, StrengthPill } from '../../components/ui';
import { ai } from '../../lib/api';
import { pct } from '../../lib/format';
import { useAsync } from '../../lib/hooks';
import type { Argument, CaseDetail } from '../../lib/types';

function Arg({ a, i, idx }: { a: Argument; i: number; idx: Map<string, string> }) {
  return (
    <motion.div className="court-arg" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 * i }}>
      <div>{a.point}{a.evidence_ids.map(id => <Cite key={id} id={id} title={idx.get(id)} />)}</div>
      <div className="row xs faint" style={{ marginTop: 4, gap: 8 }}>
        <span>{a.strength}</span>
        {a.verified && <span className="row-nw" style={{ gap: 3, color: 'var(--good-text)' }}><BadgeCheck size={12} />numbers verified</span>}
      </div>
    </motion.div>
  );
}

export function CourtTab({ k }: { k: CaseDetail }) {
  const [refresh, setRefresh] = useState(0);
  const court = useAsync(() => ai.court(k.case_id, refresh > 0), [k.case_id, refresh]);
  const [showDropped, setShowDropped] = useState(false);
  const idx = new Map([...k.evidence.map(e => [e.evidence_id, e.name] as const), ...k.peer_context.map(p => [p.evidence_id, p.metric] as const)]);

  if (court.error) return <ErrorState error={new Error(`Evidence Court needs the Part B backend on :8000 (${court.error.message}).`)} onRetry={court.reload} />;
  if (!court.data) return (
    <div className="stack">
      <p className="small muted">Prosecution and Defense are reviewing the evidence…</p>
      <div className="court"><Skeleton h={300} /><Skeleton h={300} /></div><Skeleton h={160} />
    </div>
  );
  const c = court.data;
  const v = c.verdict;

  return (
    <div className="stack">
      <div className="row between">
        <div className="small muted">Same evidence, two sides.</div>
        <div className="row">
          <span className="stamp" title={c.ai.notes[0] ?? `Model ${c.ai.model}`}><BadgeCheck size={14} />{c.verifier.kept} verified · {c.verifier.dropped} removed</span>
          <Button size="sm" variant="ghost" icon={RefreshCw} loading={court.loading} onClick={() => setRefresh(r => r + 1)}>Regenerate</Button>
        </div>
      </div>

      <div className="court">
        <div className="court-col prosecution">
          <div className="row between"><h3 className="row-nw" style={{ gap: 8 }}><Swords size={16} style={{ color: 'var(--bad)' }} />Prosecution</h3><SourceBadge source={c.prosecution.source} /></div>
          {c.prosecution.arguments.map((a, i) => <Arg key={i} a={a} i={i} idx={idx} />)}
        </div>
        <div className="court-col defense">
          <div className="row between"><h3 className="row-nw" style={{ gap: 8 }}><ShieldQuestion size={16} style={{ color: 'var(--series-1)' }} />Defense</h3><SourceBadge source={c.defense.source} /></div>
          {c.defense.arguments.map((a, i) => <Arg key={i} a={a} i={i} idx={idx} />)}
          {c.defense.missing_evidence.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div className="xs strong faint">MISSING BEFORE ANY CONCLUSION</div>
              {c.defense.missing_evidence.map(m => <div key={m} className="small muted">• {m}</div>)}
            </div>
          )}
        </div>
      </div>

      <motion.div className="verdict" initial={{ opacity: 0, scale: 0.99 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.3 }}>
        <div className="row between">
          <h3 className="row-nw" style={{ gap: 8 }}><Scale size={17} style={{ color: 'var(--accent)' }} />Verdict · human review</h3>
          <SourceBadge source={v.source} />
        </div>
        <div className="row" style={{ marginTop: 12 }}>
          <StatusPill status={v.status} />
          <span className="chip">Confidence {pct(v.confidence)}</span>
          <StrengthPill strength={v.evidence_strength} />
        </div>
        <p style={{ marginTop: 12 }}>{v.summary}</p>
        <div className="small" style={{ marginTop: 10 }}><b>Next:</b> {v.next_action_text}</div>
        <div className="divider" />
        <div className="row between">
          <span className="row-nw small strong" style={{ gap: 6 }}><UserCheck size={15} />Human approval required</span>
          <span className="xs faint">Model {c.ai.model} · {new Date(c.generated_at).toLocaleTimeString()}</span>
        </div>
      </motion.div>

      
      {c.verifier.dropped > 0 && (
        <div>
          <Button size="sm" variant="ghost" onClick={() => setShowDropped(s => !s)}>{showDropped ? 'Hide' : 'Show'} {c.verifier.dropped} removed statements</Button>
          {showDropped && (
            <div className="stack-sm" style={{ marginTop: 8 }}>
              {c.verifier.dropped_items.map((d, i) => (
                <div key={i} className="small"><span className="chip chip-bad">{d.agent}</span> <s className="muted">{d.point}</s> <span className="xs faint">({d.reason})</span></div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Icon, type IconName } from '../../components/Icon';
import { Mascot } from '../../components/Mascot';
import { Button, Card, Cite, ErrorState, Ring, Status } from '../../components/ui';
import { ai } from '../../lib/api';
import { useAsync, useInterval } from '../../lib/hooks';
import { spring } from '../../lib/theme';
import type { CaseDetail, Court } from '../../lib/types';
import { DecisionBox } from './DecisionBar';

type Turn =
  | { kind: 'banner'; text: string }
  | { kind: 'speech'; side: 'prosecution' | 'defense'; lead?: string; text: string; ids: string[] }
  | { kind: 'struck'; side: string; text: string; reason: string }
  | { kind: 'clerk' }
  | { kind: 'ruling' };

/** Turn the verified court output into a hearing: alternating statements, objections, clerk, ruling. */
function script(c: Court, caseId: string): Turn[] {
  const p = c.prosecution.arguments, d = c.defense.arguments;
  const t: Turn[] = [{ kind: 'banner', text: `Court is in session · ${caseId}` }];
  for (let i = 0; i < Math.max(p.length, d.length); i++) {
    if (p[i]) t.push({ kind: 'speech', side: 'prosecution', lead: i === 0 ? 'Opening for the prosecution.' : undefined, text: p[i].point, ids: p[i].evidence_ids });
    if (d[i]) t.push({ kind: 'speech', side: 'defense', lead: i === 0 ? 'The defense responds.' : undefined, text: d[i].point, ids: d[i].evidence_ids });
  }
  for (const s of c.verifier.dropped_items) t.push({ kind: 'struck', side: s.agent, text: s.point, reason: s.reason });
  if (c.defense.missing_evidence.length) {
    t.push({ kind: 'speech', side: 'defense', lead: 'Closing for the defense.', text: `Before anyone concludes wrongdoing, the court should see: ${c.defense.missing_evidence.map(m => m.split(':')[0]).join('; ')}.`, ids: [] });
  }
  t.push({ kind: 'banner', text: "Clerk's summary" }, { kind: 'clerk' }, { kind: 'banner', text: 'The ruling' }, { kind: 'ruling' });
  return t;
}

const SPEAKER: Record<'prosecution' | 'defense', { name: string; icon: IconName }> = {
  prosecution: { name: 'Prosecution', icon: 'inspect' },
  defense: { name: 'Defense', icon: 'shield' },
};

export function CourtRoom({ k, decide }: { k: CaseDetail; decide?: boolean }) {
  const [refresh, setRefresh] = useState(0);
  const court = useAsync(() => ai.court(k.case_id, refresh > 0), [k.case_id, refresh]);
  const turns = useMemo(() => (court.data ? script(court.data, k.case_id) : []), [court.data, k.case_id]);
  const [shown, setShown] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [steps, setSteps] = useState(false);
  const idx = new Map([...k.evidence.map(e => [e.evidence_id, e.name] as const), ...k.peer_context.map(p => [p.evidence_id, p.metric] as const)]);

  useEffect(() => { setShown(0); setPlaying(true); }, [court.data]);
  useInterval(() => { if (playing && turns.length) setShown(s => { if (s >= turns.length) { setPlaying(false); return s; } return s + 1; }); }, 1500);

  if (court.error) return <ErrorState error={new Error(`Couldn't reach the AI service (${court.error.message}).`)} onRetry={court.reload} />;
  if (!court.data) return <Card><div className="row-flex"><Mascot size={60} mood="thinking" /><p className="muted">Calling the court to order…</p></div></Card>;
  const c = court.data, v = c.verdict;
  const done = shown >= turns.length;

  const render = (t: Turn, i: number): ReactNode => {
    switch (t.kind) {
      case 'banner': return <div key={i} className="court-banner">{t.text}</div>;
      case 'speech': {
        const s = SPEAKER[t.side];
        return (
          <motion.div key={i} className={`turn ${t.side}`} initial={{ opacity: 0, y: 10, scale: .98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={spring}>
            <span className={`speaker ${t.side}`}><Icon name={s.icon} size={18} /></span>
            <div className="bubble-turn">
              <div className="turn-who">{s.name}</div>
              {t.lead && <b>{t.lead} </b>}{t.text}{t.ids.map(id => <Cite key={id} id={id} title={idx.get(id)} />)}
            </div>
          </motion.div>
        );
      }
      case 'struck': return (
        <motion.div key={i} className="struck" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <Icon name="decline" size={13} /><b>Objection sustained.</b> Struck from the record: <s>{t.text}</s> <span className="faint">({t.reason})</span>
        </motion.div>
      );
      case 'clerk': return (
        <motion.div key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={spring}>
          <Card className="card-accent">
            <div className="rec-head">
              <Ring value={v.confidence * 100} size={76} label={`Confidence ${Math.round(v.confidence * 100)} percent`}>
                <div style={{ textAlign: 'center', lineHeight: 1.1 }}><div>{Math.round(v.confidence * 100)}%</div><div style={{ fontSize: '.6rem', color: 'var(--text-3)', fontWeight: 650 }}>SURE</div></div>
              </Ring>
              <div style={{ flex: 1, minWidth: 240 }}>
                <div className="row-flex" style={{ marginBottom: 6 }}><span className="speaker clerk" style={{ width: 28, height: 28, borderRadius: 9 }}><Icon name="decision" size={14} /></span><b>The clerk</b><Status value={v.status} /></div>
                <p>{v.summary}</p>
                <p className="small muted" style={{ marginTop: 6 }}><Icon name="complete" size={12} className="inline" /> {c.verifier.kept} statements checked against the evidence{c.verifier.dropped ? `, ${c.verifier.dropped} struck` : ''}. The clerk can word the status, never change it.</p>
              </div>
            </div>
          </Card>
        </motion.div>
      );
      case 'ruling': return (
        <motion.div key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={spring}>
          {decide ? <DecisionBox k={k} /> : (
            <div className="review-box"><div className="row-nw"><Icon name="employee" size={16} /><b>The ruling is yours.</b></div>
              <p className="small" style={{ marginTop: 4 }}>Use “Human review needed” at the top of this page. Axon never rules on its own.</p></div>
          )}
        </motion.div>
      );
    }
  };

  return (
    <div className="stack-lg">
      <div className="row-flex">
        <Button size="sm" variant="tinted" icon={playing ? 'pause' : 'play'} onClick={() => { if (!playing && done) setShown(0); setPlaying(p => !p); }}>{playing ? 'Pause' : done ? 'Replay hearing' : 'Continue'}</Button>
        {!done && <Button size="sm" variant="ghost" onClick={() => { setShown(turns.length); setPlaying(false); }}>Skip to the ruling</Button>}
        <span className="spacer" />
        <span className="engine-pill" title={c.ai.notes[0] ?? c.ai.model}><Icon name="ai" size={13} />{c.prosecution.source === 'llm' ? `Argued by ${c.ai.model}` : 'Argued from templates'}</span>
        <Button size="sm" variant="ghost" icon="refresh" loading={court.loading} onClick={() => setRefresh(r => r + 1)}>New hearing</Button>
      </div>

      <Card>
        <div className="hearing">
          {turns.slice(0, shown).map(render)}
          <AnimatePresence>
            {playing && !done && turns[shown]?.kind === 'speech' && (
              <motion.div key={`typing-${shown}`} className={`turn ${(turns[shown] as { side: string }).side}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <span className={`speaker ${(turns[shown] as { side: string }).side}`}><Icon name={SPEAKER[(turns[shown] as { side: 'prosecution' | 'defense' }).side].icon} size={18} /></span>
                <div className="bubble-turn typing"><i /><i /><i /></div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </Card>

      {done && (
        <Card>
          <div className="row-flex"><h2>How this hearing was run</h2><span className="spacer" /><Button variant="ghost" size="sm" icon={steps ? 'less' : 'add'} onClick={() => setSteps(s => !s)}>{steps ? 'Hide' : 'Show'} steps</Button></div>
          {steps && <div style={{ marginTop: 16 }}><Steps c={c} /></div>}
        </Card>
      )}
    </div>
  );
}

function Steps({ c }: { c: Court }) {
  const steps: { icon: IconName; who: string; what: string; detail?: string }[] = [
    { icon: 'inspect', who: 'Prosecution agent', what: `${c.prosecution.arguments.length} points, each citing evidence`, detail: c.prosecution.source === 'llm' ? 'Gemini' : 'Template' },
    { icon: 'shield', who: 'Defense agent', what: `${c.defense.arguments.length} legitimate explanations from the same evidence`, detail: c.defense.source === 'llm' ? 'Gemini' : 'Template' },
    { icon: 'complete', who: 'Citation check', what: `${c.verifier.kept} kept, ${c.verifier.dropped} struck`, detail: 'Plain code. Drops any statement that cites missing evidence or uses a number the engine never produced.' },
    { icon: 'decision', who: 'Clerk', what: 'Words the status the engine computed', detail: c.verdict.source === 'llm' ? 'Gemini' : 'Template' },
    { icon: 'employee', who: 'You', what: 'Make the ruling' },
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

/** Case-page tab: the hearing, with the decision kept in the review box at the top of the page. */
export function CourtTab({ k }: { k: CaseDetail }) {
  return <CourtRoom k={k} />;
}

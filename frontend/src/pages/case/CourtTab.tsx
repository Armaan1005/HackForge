import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Icon, type IconName } from '../../components/Icon';
import { Mascot } from '../../components/Mascot';
import { Button, Card, Cite, ErrorState, Ring, Status } from '../../components/ui';
import { ai, courtStream, type CourtSide } from '../../lib/api';
import { useInterval } from '../../lib/hooks';
import { spring } from '../../lib/theme';
import type { CaseDetail, Court } from '../../lib/types';
import { DecisionBox } from './DecisionBar';
import { RuleChip, RulesPanel } from '../../components/Rules';

type Turn =
  | { kind: 'banner'; text: string }
  | { kind: 'speech'; side: 'prosecution' | 'defense'; lead?: string; text: string; ids: string[] }
  | { kind: 'struck'; side: string; text: string; reason: string }
  | { kind: 'clerk' }
  | { kind: 'ruling' };

type Sides = { prosecution?: CourtSide; defense?: CourtSide };

/** Turn the verified court output into a hearing: alternating statements, objections, clerk, ruling.
 * Built from whatever has streamed in so far and only ever appended to, so turns already shown never move:
 * the opening needs the prosecution, the exchange needs both sides, the clerk and ruling need the full result. */
function script(sd: Sides, c: Court | null, caseId: string): Turn[] {
  const t: Turn[] = [{ kind: 'banner', text: `Court is in session · ${caseId}` }];
  const p = sd.prosecution?.arguments, d = sd.defense?.arguments;
  if (!p) return t;
  if (p[0]) t.push({ kind: 'speech', side: 'prosecution', lead: 'Opening for the prosecution.', text: p[0].point, ids: p[0].evidence_ids });
  if (!d) return t;
  for (let i = 0; i < Math.max(p.length, d.length); i++) {
    if (p[i] && i > 0) t.push({ kind: 'speech', side: 'prosecution', text: p[i].point, ids: p[i].evidence_ids });
    if (d[i]) t.push({ kind: 'speech', side: 'defense', lead: i === 0 ? 'The defense responds.' : undefined, text: d[i].point, ids: d[i].evidence_ids });
  }
  for (const s of [...(sd.prosecution?.dropped ?? []), ...(sd.defense?.dropped ?? [])]) t.push({ kind: 'struck', side: s.agent, text: s.point, reason: s.reason });
  const missing = sd.defense?.missing_evidence ?? [];
  if (missing.length) {
    t.push({ kind: 'speech', side: 'defense', lead: 'Closing for the defense.', text: `Before anyone concludes wrongdoing, the court should see: ${missing.map(m => m.split(':')[0]).join('; ')}.`, ids: [] });
  }
  if (c) t.push({ kind: 'banner', text: "Clerk's summary" }, { kind: 'clerk' }, { kind: 'banner', text: 'The ruling' }, { kind: 'ruling' });
  return t;
}

/** A finished result as the two side events the stream would have sent (plain-endpoint fallback, AI-ready replay). */
function sidesOf(c: Court): Sides {
  const dropped = c.verifier.dropped_items;
  return {
    prosecution: { side: 'prosecution', arguments: c.prosecution.arguments, source: c.prosecution.source, model: c.ai.model, rules: c.rules, dropped: dropped.filter(d => d.agent === 'prosecutor') },
    defense: { side: 'defense', arguments: c.defense.arguments, source: c.defense.source, model: c.ai.model, rules: c.rules, dropped: dropped.filter(d => d.agent === 'defense'), missing_evidence: c.defense.missing_evidence },
  };
}

const SPEAKER: Record<'prosecution' | 'defense', { name: string; icon: IconName }> = {
  prosecution: { name: 'Prosecution', icon: 'inspect' },
  defense: { name: 'Defense', icon: 'shield' },
};

export function CourtRoom({ k, decide }: { k: CaseDetail; decide?: boolean }) {
  const [session, setSession] = useState(0); // 0 = not started; each Start/New hearing = a live AI session
  const [sides, setSides] = useState<Sides>({});
  const [c, setC] = useState<Court | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const turns = useMemo(() => script(sides, c, k.case_id), [sides, c, k.case_id]);
  const [shown, setShown] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [steps, setSteps] = useState(false);
  const idx = new Map([...k.evidence.map(e => [e.evidence_id, e.name] as const), ...k.peer_context.map(p => [p.evidence_id, p.metric] as const)]);
  const rules = c?.rules ?? [...(sides.prosecution?.rules ?? []), ...(sides.defense?.rules ?? [])].filter((r, i, a) => a.findIndex(x => x.id === r.id) === i);

  // Stream the hearing: each side starts playing the moment its verified arguments arrive.
  useEffect(() => {
    if (!session) return;
    const ctl = new AbortController();
    setSides({}); setC(null); setError(null); setShown(0); setPlaying(true); setLoading(true);
    courtStream(k.case_id, sd => setSides(prev => ({ ...prev, [sd.side]: sd })), { fresh: true, signal: ctl.signal })
      .then(full => { setSides(sidesOf(full)); setC(full); })
      .catch(() => {
        if (ctl.signal.aborted) return;
        // Streaming failed (proxy, network): fall back to the one-shot endpoint.
        return ai.court(k.case_id, false, true).then(full => { setSides(sidesOf(full)); setC(full); }, setError);
      })
      .finally(() => { if (!ctl.signal.aborted) setLoading(false); });
    return () => ctl.abort();
  }, [k.case_id, session, attempt]);

  // AI still working (slow model): the template hearing plays now; check back and replay once the AI's version is ready.
  const [polls, setPolls] = useState(0);
  useEffect(() => {
    if (!c?.ai.pending || polls >= 5) return;
    const t = setTimeout(async () => {
      try {
        const full = await ai.court(k.case_id);
        if (!full.ai.pending) { setSides(sidesOf(full)); setC(full); setShown(0); setPlaying(true); }
      } catch { /* keep the quick version */ }
      setPolls(n => n + 1);
    }, 12000);
    return () => clearTimeout(t);
  }, [c, polls, k.case_id]);
  useInterval(() => { if (playing) setShown(s => { if (s >= turns.length) { if (c) setPlaying(false); return s; } return s + 1; }); }, 1500);

  if (!session) return (
    <Card className="card-accent">
      <div className="row-flex" style={{ alignItems: 'center', gap: 20 }}>
        <Mascot size={80} mood="watching" />
        <div style={{ flex: 1, minWidth: 240 }}>
          <h2>Ready when you are</h2>
          <p className="muted small" style={{ marginTop: 4 }}>Prosecution and defense argue this case live. You make the ruling.</p>
        </div>
        <Button size="lg" icon="play" onClick={() => setSession(1)}>Start hearing</Button>
      </div>
    </Card>
  );
  if (error) return <ErrorState error={new Error(`Couldn't reach the AI service (${error.message}).`)} onRetry={() => setAttempt(n => n + 1)} />;
  const done = !!c && shown >= turns.length;
  const next = turns[shown];
  // Who the hearing is waiting on: the next scripted speaker, or (once caught up with the stream) whoever hasn't answered yet.
  const waitingOn: 'prosecution' | 'defense' | 'clerk' | null = !playing || done ? null
    : next?.kind === 'speech' ? next.side
    : shown >= turns.length && !c ? (!sides.prosecution ? 'prosecution' : !sides.defense ? 'defense' : 'clerk') : null;
  const src = sides.prosecution?.source, model = sides.prosecution?.model ?? c?.ai.model;

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
              {t.lead && <b>{t.lead} </b>}{t.text}{t.ids.map(id => /^(POL|LAW)-/.test(id) ? <RuleChip key={id} id={id} rules={rules} /> : <Cite key={id} id={id} title={idx.get(id)} />)}
            </div>
          </motion.div>
        );
      }
      case 'struck': return (
        <motion.div key={i} className="struck" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <Icon name="decline" size={13} /><b>Objection sustained.</b> Struck from the record: <s>{t.text}</s> <span className="faint">({t.reason})</span>
        </motion.div>
      );
      case 'clerk': { if (!c) return null; const v = c.verdict; return (
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
      ); }
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
        {c && !done && <Button size="sm" variant="ghost" onClick={() => { setShown(turns.length); setPlaying(false); }}>Skip to the ruling</Button>}
        <span className="spacer" />
        {src && <span className={`engine-pill ${src === 'llm' ? 'on' : ''}`} title={c?.ai.notes[0] ?? model}><Icon name="ai" size={13} />
          {src === 'llm' ? `Argued by ${model}` : c?.ai.pending ? 'AI is still preparing, showing the quick version' : 'Argued from templates'}</span>}
        <Button size="sm" variant="ghost" icon="refresh" loading={loading} onClick={() => { setPolls(0); setSession(n => n + 1); }}>New hearing</Button>
      </div>

      <Card>
        <div className="hearing">
          {turns.slice(0, shown).map(render)}
          <AnimatePresence>
            {(waitingOn === 'prosecution' || waitingOn === 'defense') && (
              <motion.div key={`typing-${shown}-${waitingOn}`} className={`turn ${waitingOn}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <span className={`speaker ${waitingOn}`}><Icon name={SPEAKER[waitingOn].icon} size={18} /></span>
                <div className="bubble-turn typing"><i /><i /><i /></div>
              </motion.div>
            )}
            {waitingOn === 'clerk' && (
              <motion.div key="typing-clerk" className="court-wait small muted" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <span className="speaker clerk" style={{ width: 28, height: 28, borderRadius: 9 }}><Icon name="decision" size={14} /></span>
                The clerk is writing the summary
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </Card>

      {done && c && <RulesPanel rules={c.rules ?? []} />}

      {done && (
        <Card>
          <div className="row-flex"><h2>How this hearing was run</h2><span className="spacer" /><Button variant="ghost" size="sm" icon={steps ? 'less' : 'add'} onClick={() => setSteps(s => !s)}>{steps ? 'Hide' : 'Show'} steps</Button></div>
          {steps && c && <div style={{ marginTop: 16 }}><Steps c={c} /></div>}
        </Card>
      )}
    </div>
  );
}

function Steps({ c }: { c: Court }) {
  const steps: { icon: IconName; who: string; what: string; detail?: string }[] = [
    { icon: 'inspect', who: 'Prosecution agent', what: `${c.prosecution.arguments.length} points, each citing evidence`, detail: c.prosecution.source === 'llm' ? 'AI (SAP AI Core)' : 'Template' },
    { icon: 'shield', who: 'Defense agent', what: `${c.defense.arguments.length} legitimate explanations from the same evidence`, detail: c.defense.source === 'llm' ? 'AI (SAP AI Core)' : 'Template' },
    { icon: 'complete', who: 'Citation check', what: `${c.verifier.kept} kept, ${c.verifier.dropped} struck`, detail: 'Plain code. Drops any statement that cites missing evidence or uses a number the engine never produced.' },
    { icon: 'course-book', who: 'Rulebook search', what: `${c.rules?.length ?? 0} policies and laws retrieved for this case`, detail: 'Keyword search (BM25) over payer rules and law summaries. Agents may cite only these; they add context, never change the score.' },
    { icon: 'decision', who: 'Clerk', what: 'Words the status the engine computed', detail: c.verdict.source === 'llm' ? 'AI (SAP AI Core)' : 'Template' },
    { icon: 'employee', who: 'You', what: 'Make the ruling' },
  ];
  return (
    <div className="trace">
      {steps.map((s, i) => (
        <div key={s.who} className={`trace-step ${i < steps.length - 1 ? 'done' : 'running'}`}>
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

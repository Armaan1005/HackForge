// "How the Fraud Twin works": the six steps of a run, drawn as a flow that follows the page's state.
// Steps 3-5 sit inside a dashed frame: they happen on a sandbox copy, never on the real queue.
import { motion } from 'motion/react';
import type { CSSProperties, ReactNode } from 'react';
import { api } from '../lib/api';
import { num, pct } from '../lib/format';
import { useAsync } from '../lib/hooks';
import type { TwinRun } from '../lib/types';

export interface TwinFlowState {
  text: string;
  recipe: { name: string; params: [string, unknown][] } | null;
  recipes: number;
  busy: 'parse' | 'run' | 'advise' | 'harden' | null;
  run: TwinRun | null;
  change: { param: string; old_value: unknown; new_value: unknown } | null;
  hardened: { before: number; after: number } | null;
}

const LAYERS = ['Rules', 'Peer anomaly', 'Timing', 'Network'];

/** Real claims (grey) with planted fakes (amber) mixed in. */
function Planted({ fakes }: { fakes: boolean }) {
  return (
    <div className="tf-dots" aria-hidden>
      {Array.from({ length: 21 }, (_, i) => <i key={i} className={fakes && i % 4 === 2 ? 'fake' : ''} />)}
    </div>
  );
}

/** The fake claims after detection: filled = caught, hollow = missed, in the run's proportion. */
function Scored({ rate }: { rate: number | null }) {
  const n = 12, caught = rate == null ? 0 : Math.round(rate * n);
  return (
    <div className="tf-dots" aria-hidden>
      {Array.from({ length: n }, (_, i) => <i key={i} className={rate == null ? 'fake hollow' : i < caught ? 'caught' : 'missed'} />)}
    </div>
  );
}

export function TwinFlow({ s }: { s: TwinFlowState }) {
  const ov = useAsync(() => api.overview(), []);
  const claims = ov.data?.tables.claims;
  const r = s.run;
  const stage = s.hardened || s.change || s.busy === 'advise' || s.busy === 'harden' ? 5 : r ? 4 : s.busy === 'run' ? 3 : s.recipe || s.busy === 'parse' ? 1 : 0;
  const running = (i: number) => (s.busy === 'parse' && i === 1) || (s.busy === 'run' && (i === 2 || i === 3)) || ((s.busy === 'advise' || s.busy === 'harden') && i === 5);

  const steps: { title: string; body: string; live?: ReactNode; visual?: ReactNode }[] = [
    { title: 'You describe a scheme', body: 'In plain words, the way a fraudster would think about it.',
      live: s.text ? <q>{s.text.length > 70 ? `${s.text.slice(0, 70)}…` : s.text}</q> : null },
    { title: 'AI picks a recipe', body: `It maps your words onto one of ${s.recipes || 6} allowed attack recipes, each with safe limits. Anything else is refused.`,
      live: s.recipe ? <><b>{s.recipe.name}</b>{s.recipe.params.slice(0, 3).map(([k, v]) => <span key={k}>{k.replace(/_/g, ' ')} {String(v)}</span>)}</> : null },
    { title: 'Copy and plant fake claims', body: `${claims ? num(claims) : 'All'} real claims are copied. Fake ones are planted in the copy, some deliberately mild.`,
      live: r ? <b>{num(r.generated)} fake claims planted</b> : null, visual: <Planted fakes={stage >= 2} /> },
    { title: 'Run detection again', body: 'The same checks that build the real queue run on the copy.',
      live: <span className="tf-layers">{LAYERS.map(l => <span key={l}>{l}</span>)}</span> },
    { title: 'Score it', body: 'How many fakes were caught or missed, and whether real claims got more false alarms.',
      live: r ? <><b>{pct(r.detection_rate, 0)} caught</b><span>{num(r.detected)} of {num(r.generated)}</span><span>false alarms {pct(r.false_positive_rate.baseline, 1)} → {pct(r.false_positive_rate.run, 1)}</span></> : null,
      visual: <Scored rate={r ? r.detection_rate : null} /> },
    { title: 'Fix the gap, you approve', body: 'AI suggests one setting change. It is re-tested on the same fake claims before anyone accepts it.',
      live: s.change ? <><b>{s.change.param.replace(/_/g, ' ').toLowerCase()}: {String(s.change.old_value)} → {String(s.change.new_value)}</b>
        {s.hardened && <span>caught {pct(s.hardened.before, 0)} → {pct(s.hardened.after, 0)}</span>}</> : r && r.missed === 0 ? <span>Nothing missed, nothing to fix.</span> : null },
  ];

  return (
    <div className="tf" role="list" aria-label="How the Fraud Twin works">
      <div className="tf-sandbox" aria-hidden><span>Sandbox copy · the real queue is never touched</span></div>
      {steps.map((st, i) => {
        const state = running(i) ? 'running' : i < stage ? 'done' : i === stage ? 'active' : 'todo';
        return (
          <motion.div key={st.title} role="listitem" className={`tf-step tf-s${i + 1} ${state}`} style={{ '--i': i + 1 } as CSSProperties}
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * .05 }}>
            <span className="tf-n">{String(i + 1).padStart(2, '0')}</span>
            <b className="tf-title">{st.title}</b>
            <p className="tf-body">{st.body}</p>
            {st.visual}
            {st.live && <div className="tf-live">{st.live}</div>}
          </motion.div>
        );
      })}
      <div className="tf-legend" aria-hidden>
        <span><i />real claim</span><span><i className="fake" />planted fake</span><span><i className="caught" />caught</span><span><i className="missed" />missed</span>
      </div>
    </div>
  );
}

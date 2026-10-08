import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Icon, type IconName } from '../components/Icon';
import { MascotMark } from '../components/Mascot';
import { Button, ErrorState, PageHeader, Skeleton } from '../components/ui';
import { api } from '../lib/api';
import { inr, PATTERN, pct } from '../lib/format';
import { useAsync } from '../lib/hooks';
import type { CaseDetail } from '../lib/types';

// ── Script timing (ms). One clock drives everything, so pause / skip / replay are exact. ──
const sum = (a: number[]) => a.reduce((x, y) => x + y, 0);
const ACT1 = [3, 3, 3.5, 3.5, 3.5, 3.5, 3.5, 3.5, 4].map(s => s * 1000);  // ~32 s with Axon
const ACT2 = [3.5, 3.5, 3.5, 1, 1, 1, 1, 1, 5].map(s => s * 1000);    // ~21 s without: detection steps flash by greyed out
const REWIND = 3000, STRIKE = 2600;
const A1_END = sum(ACT1), A2_START = A1_END + REWIND, A2_END = A2_START + sum(ACT2), STRIKE_END = A2_END + STRIKE, END = STRIKE_END + 400;
const DETECTION = new Set([3, 4, 5, 6, 7]);
const start1 = (i: number) => sum(ACT1.slice(0, i));
const start2 = (i: number) => A2_START + sum(ACT2.slice(0, i));

type Phase = 'act1' | 'rewind' | 'act2' | 'strike' | 'cta';
const clamp = (v: number) => Math.max(0, Math.min(1, v));
const easeOut = (p: number) => 1 - (1 - p) ** 3;

function locate(durs: number[], t: number) {
  let acc = 0;
  for (let i = 0; i < durs.length; i++) { if (t < acc + durs[i]) return { i, p: (t - acc) / durs[i] }; acc += durs[i]; }
  return { i: durs.length - 1, p: 1 };
}

function at(t: number): { phase: Phase; i: number; p: number } {
  if (t < A1_END) return { phase: 'act1', ...locate(ACT1, t) };
  if (t < A2_START) { const p = (t - A1_END) / REWIND; return { phase: 'rewind', i: Math.round(8 * (1 - easeOut(p))), p }; }
  if (t < A2_END) return { phase: 'act2', ...locate(ACT2, t - A2_START) };
  if (t < STRIKE_END) return { phase: 'strike', i: 8, p: (t - A2_END) / STRIKE };
  return { phase: 'cta', i: 8, p: 1 };
}

// ── Dates ──
const D = (s: string) => new Date(`${s.slice(0, 10)}T00:00:00`);
const fmt = (d: Date) => d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
const fmtShort = (d: Date) => d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });

interface Block { icon: IconName; offIcon?: IconName; title: string; a1: string; a2?: string; title2?: string }
interface Note { block: number; delay: number;  /* share of the step's duration */ app: 'axon' | 'claims'; title: string; body: string }

/** Everything shown is read from the engine's case: no figures are typed in here. */
function story(k: CaseDetail) {
  const cs = k.claims_summary, m = k.money, clock = k.payment_clock;
  const release = clock.next_release_date ? D(clock.next_release_date) : null;
  const today = release && clock.days_until_release != null ? new Date(release.getTime() - clock.days_until_release * 864e5) : new Date();
  const tl = [...k.timeline].sort((a, b) => a.date.localeCompare(b.date));
  const first = D((tl.find(e => e.event_type === 'first_claim') ?? tl[0])?.date ?? today.toISOString());
  const providers = k.entities.filter(e => e.entity_type === 'provider').length || k.network_summary.community_size;
  const records = new Set(tl.filter(e => e.event_type === 'document_created').map(e => e.description.split(' ')[0])).size;
  const methods = Object.keys(k.scores.by_method).length;
  const limit = inr(cs.review_threshold, false);
  const end = release ?? today;
  const dates = [first, first, first, today, today, today, today, today, end];
  const left = clock.days_until_release ?? 0;

  const blocks: Block[] = [
    { icon: 'building', title: 'Clinics treat patients', a1: `${providers} linked providers · ${k.member_harm.members_affected} members` },
    { icon: 'receipt', title: 'Claims reach the insurer', a1: `${cs.claim_count} claims worth ${inr(cs.amount_total)}, starting ${fmt(first)}` },
    { icon: 'inspection', title: 'Insurer intake', a1: `Each claim stays under the ${limit} review limit (largest ${inr(cs.amount_max, false)}). Axon looks at them together.`,
      a2: `Each claim stays under the ${limit} review limit, so each one is approved on its own.` },
    { icon: 'trend-up', title: 'Anomaly models', a1: `${k.scores.methods_agreeing} of ${methods} detection methods agree · risk ${k.scores.risk}` },
    { icon: 'connected', title: 'Network map', a1: `${k.network_summary.community_size} providers in one tight group · ${k.network_summary.connected_claims} connected claims` },
    { icon: 'document-text', title: 'Records check', a1: `${records} medical records flagged for a person to verify` },
    { icon: 'decision', title: 'Evidence Court', a1: `Prosecution and defense argue the same evidence · ${k.evidence_strength} evidence, ${pct(k.confidence)} sure` },
    { icon: 'employee', title: 'Investigator decides', a1: `Priya reviews and holds the ${clock.pending_claims} claims still waiting to be paid` },
    { icon: 'locked', offIcon: 'money-bills', title: 'Payment held', title2: 'Payment released',
      a1: `${inr(clock.pending_amount)} stopped before ${fmt(end)} · ${inr(m.expected_recovery)} to recover from claims already paid`,
      a2: `${inr(cs.amount_total)} paid out across ${cs.claim_count} claims. Nothing flagged, nothing to recover.` },
  ];

  const say1 = [
    `${fmt(first)}. ${providers} linked clinics start treating patients.`,
    `They send ${cs.claim_count} claims, worth ${inr(cs.amount_total)} in total.`,
    `Every claim stays just under the ${limit} review limit. One by one, each looks normal.`,
    'Axon’s models catch the pattern across all of them.',
    `It maps the network: ${k.network_summary.community_size} providers acting as one.`,
    'It checks the medical records behind the claims.',
    'Prosecution and defense argue it out. Every claim they make is checked.',
    'A person makes the call. Axon never does.',
    `${inr(clock.pending_amount)} is stopped before it’s paid.`,
  ];
  const say2 = [
    `Same clinics, same patients. ${fmt(first)}.`,
    `The same ${cs.claim_count} claims arrive.`,
    'Each one is under the limit, so each one is approved.',
    'No model looks at the pattern.', 'No one maps the network.', 'No one checks the records.', 'No hearing.', 'No one is asked.',
    `${fmt(end)}. The last ${clock.pending_claims} claims are paid. It’s all gone.`,
  ];

  const notes: Note[] = [
    { block: 3, delay: 0.55, app: 'axon', title: 'Pattern found', body: `${PATTERN[k.pattern] ?? k.pattern} · risk ${k.scores.risk}` },
    { block: 4, delay: 0.55, app: 'axon', title: 'Network linked', body: `${k.network_summary.community_size} providers · ${k.network_summary.connected_claims} claims` },
    { block: 5, delay: 0.55, app: 'axon', title: 'Records flagged', body: `${records} records need a look` },
    { block: 6, delay: 0.6, app: 'axon', title: 'Hearing finished', body: `${k.evidence_strength} evidence · a person decides` },
    { block: 7, delay: 0.6, app: 'axon', title: 'Hold approved by Priya', body: `${clock.pending_claims} claims · ${inr(clock.pending_amount)}` },
    { block: 8, delay: 0.4, app: 'axon', title: 'Payment held', body: `${inr(clock.pending_amount)} stays with you` },
  ];
  const notes2: Note[] = [
    { block: 2, delay: 0.6, app: 'claims', title: 'Claims approved', body: `${cs.claim_count} claims, each under ${limit}` },
    { block: 7, delay: 0.3, app: 'claims', title: 'Payments sent', body: `${inr(m.paid)} paid` },
    { block: 8, delay: 0.55, app: 'claims', title: 'Payment run complete', body: `${inr(clock.pending_amount)} paid on ${fmt(end)}` },
  ];
  return { blocks, dates, say1, say2, notes, notes2, today, end, left };
}

// ── Phone ──
function Phone({ k, s, t, phase }: { k: CaseDetail; s: ReturnType<typeof story>; t: number; phase: Phase }) {
  const total = k.claims_summary.amount_total;
  const caught = total * clamp((t - start1(3)) / (start1(6) - start1(3)));
  const linked = Math.round(k.claims_summary.claim_count * clamp((t - start1(3)) / (start1(6) - start1(3))));
  const paidOut = total * clamp((t - start2(2)) / (A2_END - start2(2)));
  const act2 = phase === 'act2' || phase === 'strike' || phase === 'cta';
  const struck = phase === 'strike' || phase === 'cta';
  const notes = phase === 'act1' ? s.notes.filter(n => t >= start1(n.block) + n.delay * ACT1[n.block])
    : act2 ? s.notes2.filter(n => t >= start2(n.block) + n.delay * ACT2[n.block]) : [];
  const date = phase === 'cta' ? s.today : s.dates[at(t).i];

  return (
    <div className={`iphone ${act2 ? 'muted' : ''} ${struck ? 'struck' : ''}`} aria-label="Phone view of the insurer's money">
      <div className="iphone-screen">
        <div className="iphone-island" />
        <div className="iphone-status"><span>9:41</span><span className="iphone-bars"><i /><i /><i /><i /></span></div>
        <div className="iphone-lock">
          <div className="iphone-date">{fmtShort(date)}</div>
          <div className="iphone-time">9:41</div>
        </div>

        <div className={`iphone-widget ${struck ? 'lost' : ''}`}>
          <div className="row-flex xs" style={{ gap: 6 }}><MascotMark size={16} /><b>{struck ? 'Without Axon' : 'Caught by Axon'}</b></div>
          <div className="iphone-amount">
            <span className="amt">{inr(phase === 'act1' ? caught : total)}</span>
            {struck && <motion.span className="strike-line" initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: .55, delay: .35, ease: [.22, 1, .36, 1] }} />}
          </div>
          <div className="xs iphone-sub">
            {struck ? 'Lost. Paid out, never flagged.'
              : act2 ? `Paid out so far: ${inr(paidOut)}`
              : t < start1(3) ? 'Watching every claim' : t < start1(8) ? `${linked} of ${k.claims_summary.claim_count} claims linked`
              : `${inr(k.payment_clock.pending_amount)} held · ${inr(k.money.expected_recovery)} to recover`}
          </div>
        </div>

        <div className="iphone-notes">
          <AnimatePresence initial={false}>
            {[...notes].reverse().slice(0, phase === 'cta' ? 2 : 4).map(n => (
              <motion.div key={n.app + n.title} layout className="iphone-note"
                initial={{ opacity: 0, y: -16, scale: .96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, scale: .9 }}
                transition={{ type: 'spring', stiffness: 420, damping: 34 }}>
                <span className={`note-app ${n.app}`}>{n.app === 'axon' ? <MascotMark size={18} /> : <Icon name="money-bills" size={14} />}</span>
                <div><b>{n.title}</b><span>{n.body}</span></div>
                <span className="note-when">now</span>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>

        <AnimatePresence>
          {phase === 'cta' && (
            <motion.div className="iphone-cta" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: .1 }}>
              <b>{inr(k.payment_clock.pending_amount)} still holdable</b>
              <span>releases in {s.left} day{s.left === 1 ? '' : 's'}</span>
            </motion.div>
          )}
        </AnimatePresence>
        <div className="iphone-home" />
      </div>
    </div>
  );
}

// ── Page ──
export function Timelines() {
  const [params] = useSearchParams();
  const id = params.get('case') ?? 'CASE-0002';
  const kq = useAsync(() => api.case(id), [id]);
  const [t, setT] = useState(() => Math.min(END, Math.max(0, Number(params.get('at') ?? 0) * 1000 || 0)));  // ?at=35 starts at Act 2
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing) return;
    let raf = 0, last = performance.now();
    const tick = (now: number) => { setT(x => Math.min(END, x + (now - last))); last = now; raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]);
  useEffect(() => { if (t >= END) setPlaying(false); }, [t]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.code !== 'Space' || (e.target as HTMLElement).closest('input, textarea, button')) return;
      e.preventDefault(); setPlaying(p => { if (!p && t >= END) setT(0); return !p; });
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [t]);

  const s = useMemo(() => (kq.data ? story(kq.data) : null), [kq.data]);
  if (kq.error) return <ErrorState error={kq.error} onRetry={kq.reload} />;
  if (!kq.data || !s) return <Skeleton h={600} />;
  const k = kq.data;

  const { phase, i, p } = at(t);
  const act2 = phase !== 'act1' && phase !== 'rewind';
  const started = t > 0;
  const say = !started ? 'Press play. Same data, same dates, two outcomes.'
    : phase === 'act1' ? s.say1[i] : phase === 'rewind' ? 'Rewind. Same claims, same dates. This time, without Axon.'
    : phase === 'act2' ? s.say2[i] : phase === 'strike' ? `Without Axon, ${inr(k.claims_summary.amount_total)} is lost.`
    : `Back to today: ${inr(k.payment_clock.pending_amount)} can still be held. It releases in ${s.left} day${s.left === 1 ? '' : 's'}.`;
  const rewindDate = phase === 'rewind' ? new Date(s.dates[8].getTime() - (s.dates[8].getTime() - s.dates[0].getTime()) * easeOut(p)) : null;
  const date = phase === 'cta' ? s.today : rewindDate ?? s.dates[i];
  const fill = phase === 'rewind' ? (i + .5) / 9 : (i + (phase === 'act1' || phase === 'act2' ? p : 1)) / 9;
  const play = () => { if (t >= END) setT(0); setPlaying(v => !v); };

  return (
    <div className={`tl ${act2 ? 'tl-act2' : ''} ${phase === 'rewind' ? 'tl-rewind' : ''} ${phase === 'strike' || phase === 'cta' ? 'tl-lost' : ''}`}>
      <PageHeader eyebrow="Two timelines"
        title={phase === 'cta' ? 'Back to today' : act2 || phase === 'rewind' ? 'The same days, without Axon' : 'With Axon'}
        subtitle={<>One real case from the engine, {k.case_id} ({PATTERN[k.pattern] ?? k.pattern}). Same data, same dates, two outcomes.</>}
        actions={<div className="row-flex">
          <Button icon={playing ? 'pause' : 'play'} onClick={play}>{playing ? 'Pause' : t >= END ? 'Replay' : started ? 'Continue' : 'Play'}</Button>
          {started && <Button variant="ghost" icon="refresh" onClick={() => { setT(0); setPlaying(true); }}>Restart</Button>}
          {t < A2_END && <Button variant="ghost" onClick={() => { setT(A2_END); setPlaying(true); }}>Skip to the end</Button>}
        </div>} />

      <div className="tl-grid">
        <div className="tl-main card">
          <div className="tl-top">
            <div className={`tl-act ${act2 ? 'off' : ''}`}>{act2 || phase === 'rewind' ? 'Without Axon' : 'With Axon'}</div>
            <div className="tl-date"><Icon name="calendar" size={14} />{fmt(date)}</div>
            <div className="tl-progress" aria-hidden><span style={{ width: `${(t / END) * 100}%` }} /></div>
          </div>
          <p className="tl-say" aria-live="polite">{say}</p>

          <div className="tl-pipe">
            <div className="tl-rail"><span style={{ height: `${fill * 100}%` }} /></div>
            {s.blocks.map((b, n) => {
              const off = act2 && DETECTION.has(n);
              const state = !started ? 'todo' : n < i ? 'done' : n === i ? 'active' : 'todo';
              const lostRow = act2 && n === 8 && (phase !== 'act2' || state === 'active');
              return (
                <div key={n} className={`tl-step ${state} ${off ? 'off' : ''} ${lostRow ? 'lost' : ''}`}>
                  <span className="tl-node"><Icon name={off ? 'hide' : act2 && b.offIcon ? b.offIcon : state === 'done' && !act2 ? 'accept' : b.icon} size={16} /></span>
                  <div className="tl-body">
                    <div className="tl-title">{act2 && b.title2 ? b.title2 : b.title}{off && <span className="tl-tag">Not in place</span>}</div>
                    {!off && <div className="tl-detail">{act2 && b.a2 ? b.a2 : b.a1}</div>}
                    {state === 'active' && (phase === 'act1' || phase === 'act2') && <div className="tl-bar"><span style={{ width: `${p * 100}%` }} /></div>}
                  </div>
                  <span className="tl-when">{fmt(s.dates[n]).replace(/ \d{4}$/, '')}</span>
                </div>
              );
            })}
          </div>
          {phase === 'rewind' && <div className="tl-rewind-badge" aria-hidden><Icon name="undo" size={22} /> Rewind</div>}
        </div>

        <div className="tl-side">
          <Phone k={k} s={s} t={t} phase={phase} />
          <AnimatePresence>
            {phase === 'cta' && (
              <motion.div className="tl-cta" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
                <b>{inr(k.payment_clock.pending_amount)} still holdable · releases in {s.left} day{s.left === 1 ? '' : 's'}</b>
                <span className="small muted">It hasn’t happened yet. A person can still act today.</span>
                <div className="row-flex" style={{ marginTop: 10 }}>
                  <Link to={`/cases/${k.case_id}`} className="btn btn-primary btn-sm"><Icon name="arrow-right" size={14} />Open the case</Link>
                  <Button size="sm" variant="ghost" icon="refresh" onClick={() => { setT(0); setPlaying(true); }}>Replay</Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

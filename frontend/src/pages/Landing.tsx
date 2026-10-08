import { motion } from 'motion/react';
import { Link } from 'react-router-dom';
import { AreaTrend, weekly } from '../components/AreaTrend';
import { Globe } from '../components/Globe';
import { Icon, type IconName } from '../components/Icon';
import { MascotMark } from '../components/Mascot';
import { Skeleton } from '../components/ui';
import { api } from '../lib/api';
import { inr, num } from '../lib/format';
import { useAsync } from '../lib/hooks';
import type { Claim } from '../lib/types';

const STEPS: { icon: IconName; title: string; body: string; to: string }[] = [
  { icon: 'inspect', title: 'Detect', body: 'Rules, anomaly models, timing checks and a network map look at every claim line together.', to: '/home' },
  { icon: 'accept', title: 'Explain away', body: 'Before anything reaches you, Axon tries to clear it: sicker patients, a rural sole provider, a seasonal surge.', to: '/explained' },
  { icon: 'decision', title: 'Argue', body: 'A prosecution and a defense agent argue from the same evidence. Every line is checked against it.', to: '/court' },
  { icon: 'employee', title: 'Decide', body: 'A person makes every call. Axon never denies a claim or holds a payment on its own.', to: '/queue' },
];

const rise = { initial: { opacity: 0, y: 16 }, whileInView: { opacity: 1, y: 0 }, viewport: { once: true, margin: '-60px' }, transition: { duration: .5, ease: [.22, 1, .36, 1] as const } };

export function Landing() {
  const ov = useAsync(() => api.overview(), []);
  const q = useAsync(() => api.queue(40, 30), []);
  const claims = useAsync(async () => {
    const ids = (await api.queue(40, 30)).cases.map(c => c.case_id);
    const all = await Promise.all(ids.map(id => api.claims(id).then(r => r.claims).catch(() => [] as Claim[])));
    return { cases: ids.length, weeks: weekly(all.flat()) };
  }, []);

  const f = ov.data?.funnel;
  const atStake = q.data?.cases.reduce((s, c) => s + c.dollars_at_risk, 0);
  const holdable = q.data?.cases.filter(c => c.hold_recommended).length;
  const stats = f ? [
    { v: num(f.claim_lines), l: 'claim lines checked' },
    { v: num(f.alerts), l: 'alerts raised' },
    { v: num(f.explained), l: 'explained away before reaching anyone' },
    { v: num(f.cases), l: 'cases for a person to review' },
  ] : [];

  return (
    <div className="landing">
      <header className="landing-nav container">
        <Link to="/" className="brand"><MascotMark size={30} />Axon</Link>
        <nav className="landing-links">
          <Link to="/timelines">Two timelines</Link>
          <Link to="/rulebook">Rulebook</Link>
          <Link to="/trust">Trust</Link>
        </nav>
        <Link to="/home" className="btn btn-primary btn-sm">Open workspace<Icon name="arrow-right" size={14} /></Link>
      </header>

      <section className="landing-hero container">
        <motion.div className="hero-copy" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .6, ease: [.22, 1, .36, 1] }}>
          <h1 className="hero-title">ClaimShield Nexus</h1>
          <p className="hero-sub">A unified platform that identifies suspicious claims and coordinated networks, predicts future risk, explains the evidence, and prioritizes cases for Special Investigations Unit review.</p>
          <div className="row-flex" style={{ gap: 10, marginTop: 26 }}>
            <Link to="/home" className="btn btn-primary btn-md">Open workspace<Icon name="arrow-right" size={15} /></Link>
            <Link to="/timelines" className="btn btn-secondary btn-md"><Icon name="play" size={14} />Watch two timelines</Link>
          </div>
          <p className="xs faint" style={{ marginTop: 18 }}>Synthetic data only. Advisory: a person decides every case.</p>
        </motion.div>

        <div className="hero-globe">
          <Globe />
          {q.data && (
            <>
              <motion.div className="globe-card a" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: .6 }}>
                <span className="globe-dot" /><div><b>{inr(atStake)}</b><span>at stake in {q.data.cases.length} open cases</span></div>
              </motion.div>
              <motion.div className="globe-card b" initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: .8 }}>
                <span className="globe-dot warn" /><div><b>{holdable} case{holdable === 1 ? '' : 's'}</b><span>with payments still holdable</span></div>
              </motion.div>
            </>
          )}
        </div>
      </section>

      <section className="container">
        <motion.div className="landing-stats" {...rise}>
          {stats.length ? stats.map(s => <div key={s.l} className="landing-stat"><b>{s.v}</b><span>{s.l}</span></div>) : <Skeleton h={88} />}
        </motion.div>
      </section>

      <section className="container landing-section">
        <motion.div {...rise}>
          {claims.data ? (
            <AreaTrend title="Money moving through flagged cases" today={ov.data?.sim_today ?? new Date().toISOString().slice(0, 10)}
              description={`Billed per week across the ${claims.data.cases} open cases. Amber has already been paid out; green can still be stopped.`}
              data={claims.data.weeks} />
          ) : <Skeleton h={360} />}
        </motion.div>
      </section>

      <section className="container landing-section">
        <motion.h2 className="landing-h2" {...rise}>How a case gets to you</motion.h2>
        <div className="landing-steps">
          {STEPS.map((s, i) => (
            <motion.div key={s.title} {...rise} transition={{ ...rise.transition, delay: i * .08 }}>
              <Link to={s.to} className="landing-step">
                <span className="landing-step-n">{i + 1}</span>
                <span className="row-icon"><Icon name={s.icon} size={16} /></span>
                <b>{s.title}</b>
                <p className="small muted">{s.body}</p>
              </Link>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="container landing-section">
        <motion.div className="landing-book" {...rise}>
          <Link to="/rulebook" className="mini-book" aria-label="Open the rulebook">
            <span className="mini-book-spine" /><span className="mini-book-cover"><MascotMark size={34} /><b>Axon Rulebook</b><small>Payer rules · law summaries</small></span>
          </Link>
          <div>
            <h2 className="landing-h2" style={{ margin: 0 }}>Every argument opens the rulebook</h2>
            <p className="muted" style={{ marginTop: 8, maxWidth: 560 }}>For each case, Axon looks up the few payer rules and law summaries that apply. The agents may cite only those pages, and every number must still come from the claims.</p>
            <Link to="/rulebook" className="btn btn-secondary btn-sm" style={{ marginTop: 14 }}><Icon name="course-book" size={14} />Read the rulebook</Link>
          </div>
        </motion.div>
      </section>

      <footer className="container landing-foot small faint">
        <span>Axon · built on synthetic data for a hackathon. Not legal advice; law summaries must be checked against the official text.</span>
        <Link to="/home">Open workspace</Link>
      </footer>
    </div>
  );
}

import { motion } from 'motion/react';
import { Link } from 'react-router-dom';
import { AreaTrend, weekly } from '../components/AreaTrend';
import { Globe } from '../components/Globe';
import { Icon } from '../components/Icon';
import { MascotMark } from '../components/Mascot';
import { Skeleton } from '../components/ui';
import { api } from '../lib/api';
import { inr, num } from '../lib/format';
import { useAsync } from '../lib/hooks';
import type { Claim } from '../lib/types';

const STEPS: { title: string; body: string; to: string; where: string }[] = [
  { title: 'Detect', body: 'Rules, anomaly models, timing checks and a network map read every claim line together, so a ring of small claims shows up as one pattern.', to: '/home', where: 'Home' },
  { title: 'Explain away', body: 'Before anything reaches a person, Axon tries the innocent readings first: sicker patients, a rural sole provider, a seasonal surge.', to: '/explained', where: 'Explained' },
  { title: 'Argue', body: 'A prosecution and a defense agent argue from the same evidence. Anything they can’t back with a number from the claims is struck.', to: '/court', where: 'Evidence Court' },
  { title: 'Decide', body: 'Cases are ranked against the team’s hours. A person makes every call; nothing is denied or held automatically.', to: '/queue', where: 'Cases' },
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
  // The funnel, as the engine reports it: everything read, down to what a person looks at today.
  const stats = f ? [
    { v: num(f.claim_lines), l: 'claim lines read' },
    { v: num(f.alerts), l: 'alerts raised' },
    { v: num(f.explained), l: 'explained away' },
    { v: num(f.cases), l: 'cases built' },
    { v: num(f.selected_today), l: `picked for today’s ${f.capacity_hours} review hours` },
  ] : [];
  const asOf = ov.data ? new Date(`${ov.data.sim_today}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '';

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
        <motion.div {...rise}>
          {stats.length ? (
            <>
              <div className="ledger">
                {stats.map((s, i) => (
                  <div key={s.l} className={`ledger-item ${i === stats.length - 1 ? 'last' : ''}`}>
                    {i > 0 && <Icon name="slim-arrow-right" size={14} className="ledger-arrow" />}
                    <b>{s.v}</b><span>{s.l}</span>
                  </div>
                ))}
              </div>
              <p className="ledger-note">Engine run as of {asOf} · synthetic data, seed {ov.data?.seed}</p>
            </>
          ) : <Skeleton h={88} />}
        </motion.div>
      </section>

      <section className="container landing-section">
        <motion.div {...rise}>
          {claims.data ? (
            <AreaTrend title="Money moving through flagged cases" today={ov.data?.sim_today ?? new Date().toISOString().slice(0, 10)}
              description={`Billed per week across the ${claims.data.cases} open cases. Amber has already been paid out; green can still be stopped.`}
              data={claims.data.weeks}
              source={`Axon engine, claims table (service_date, billed_amount, payment_status) · synthetic data${ov.data ? `, seed ${ov.data.seed}` : ''}`} />
          ) : <Skeleton h={360} />}
        </motion.div>
      </section>

      <section className="container landing-section">
        <div className="how">
          <motion.div className="how-head" {...rise}>
            <p className="eyebrow">How it works</p>
            <h2 className="landing-h2">How a case gets to you</h2>
            <p className="muted small">Four stages. Each one has its own page in the workspace, so you can check the work.</p>
          </motion.div>
          <ol className="how-list">
            {STEPS.map((s, i) => (
              <motion.li key={s.title} {...rise} transition={{ ...rise.transition, delay: i * .06 }}>
                <Link to={s.to} className="how-row">
                  <span className="how-n">{String(i + 1).padStart(2, '0')}</span>
                  <div><b>{s.title}</b><p>{s.body}</p></div>
                  <span className="how-where">{s.where}<Icon name="arrow-right" size={13} /></span>
                </Link>
              </motion.li>
            ))}
          </ol>
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

import { motion } from 'motion/react';
import { Link } from 'react-router-dom';
import { Icon, type IconName } from '../components/Icon';
import { Mascot, MascotMark } from '../components/Mascot';
import { fade, spring } from '../lib/theme';
import './landing.css';

const features: { icon: IconName; title: string; body: string }[] = [
  { icon: 'org-chart', title: 'Connected claims tell the truth', body: 'Six ₹40K claims look normal alone. Axon links providers, owners, members and timing to expose the network behind them.' },
  { icon: 'complete', title: 'Explains alerts away first', body: 'Every alert is tested against innocent explanations (rural access, sicker patients, seasonal spikes) before a human sees it.' },
  { icon: 'document-text', title: 'Catches fabricated records', body: 'Documents are cross-checked against claims to spot inserted consults, edited dates and copied signatures.' },
  { icon: 'money-bills', title: 'Money clock', body: 'See which suspicious payments release in the next days, with a hold recommendation a human approves.' },
  { icon: 'target-group', title: 'Investigator-hours optimizer', body: 'Ranks cases as a portfolio against your team’s real capacity, with a plain reason for every pick.' },
  { icon: 'lab', title: 'Fraud Twin', body: 'Axon attacks itself with tomorrow’s fraud, explains what it missed and proposes a safe fix.' },
];

const steps = ['Detect with 4 methods', 'Explain the innocent away', 'Build evidence-backed cases', 'Rank by recovery per hour', 'A human decides'];

const stats = [
  { num: '97%', label: 'precision on planted fraud' },
  { num: '0', label: 'real frauds wrongly cleared' },
  { num: '109 → 8', label: 'alerts → cases worth a look' },
  { num: '< 1 s', label: 'to re-plan the queue' },
];

const rise = (d = 0) => ({ initial: { opacity: 0, y: 14 }, whileInView: { opacity: 1, y: 0 }, viewport: { once: true }, transition: { ...fade, delay: d } });

export function Landing() {
  return (
    <div className="lp">
      <div className="container">
        <header className="lp-nav">
          <Link to="/welcome" className="brand" aria-label="Axon"><MascotMark size={30} />Axon <small>for SIU teams</small></Link>
          <nav className="links">
            <a href="#how" className="btn btn-ghost btn-sm hide-sm">How it works</a>
            <a href="#features" className="btn btn-ghost btn-sm hide-sm">Features</a>
            <Link to="/login" className="btn btn-secondary btn-sm">Sign in</Link>
          </nav>
        </header>

        <section className="lp-hero">
          <motion.div {...rise()}>
            <span className="lp-tag"><span className="dot" />Fraud, waste &amp; abuse intelligence</span>
            <h1>Connected claims <em>tell the truth.</em></h1>
            <p className="lead">Axon finds the fraud networks hiding in plain sight, explains away the noise, and puts the few cases that matter in front of your investigators before the money leaves.</p>
            <div className="lp-cta">
              <Link to="/login" className="btn btn-primary btn-lg"><Icon name="arrow-right" size={17} />Get started</Link>
              <a href="#how" className="btn btn-secondary btn-lg"><Icon name="play" size={16} />See how it works</a>
            </div>
          </motion.div>

          <motion.div className="lp-visual" initial={{ opacity: 0, scale: .96 }} animate={{ opacity: 1, scale: 1 }} transition={{ ...spring, delay: .1 }}>
            <Mascot size={220} mood="watching" />
            <motion.div className="lp-float" style={{ top: 30, left: 0 }} animate={{ y: [0, -6, 0] }} transition={{ duration: 5, repeat: Infinity }}>
              <Icon name="status-critical" size={18} /><span><b>₹5.34L</b><span className="muted">held before release</span></span>
            </motion.div>
            <motion.div className="lp-float" style={{ bottom: 40, right: 0 }} animate={{ y: [0, 6, 0] }} transition={{ duration: 6, repeat: Infinity }}>
              <Icon name="org-chart" size={18} /><span><b>3 providers, 1 owner</b><span className="muted">47 connected claims</span></span>
            </motion.div>
            <motion.div className="lp-float" style={{ bottom: 150, left: -10 }} animate={{ y: [0, -5, 0] }} transition={{ duration: 7, repeat: Infinity }}>
              <Icon name="accept" size={18} /><span><b>27 alerts</b><span className="muted">explained away</span></span>
            </motion.div>
          </motion.div>
        </section>

        <section className="lp-stats">
          {stats.map((s, i) => (
            <motion.div key={s.label} className="card lp-stat" {...rise(i * .05)}>
              <div className="num tabular">{s.num}</div><div className="small muted">{s.label}</div>
            </motion.div>
          ))}
        </section>

        <section id="features">
          <div className="lp-section-title"><div className="eyebrow">Why Axon</div><h2>Evidence first. Humans decide.</h2></div>
          <div className="lp-grid">
            {features.map((f, i) => (
              <motion.div key={f.title} className="card lp-feature" {...rise(i * .04)}>
                <div className="ico"><Icon name={f.icon} size={22} /></div>
                <h3>{f.title}</h3><p className="small muted">{f.body}</p>
              </motion.div>
            ))}
          </div>
        </section>

        <section id="how">
          <div className="lp-section-title"><div className="eyebrow">How it works</div><h2>From thousands of alerts to a short, trusted list</h2></div>
          <div className="lp-steps">
            {steps.map((s, i) => (
              <motion.div key={s} className="card lp-step" {...rise(i * .05)}>
                <div className="n">{i + 1}</div><b>{s}</b>
              </motion.div>
            ))}
          </div>
        </section>

        <motion.section className="card card-accent lp-final" {...rise()}>
          <Mascot size={80} mood="happy" />
          <h2 style={{ marginTop: 12 }}>Stop the money before it leaves</h2>
          <p className="muted" style={{ margin: '8px auto 20px', maxWidth: 520 }}>Code computes every score and rupee figure. AI only explains. A human always makes the final call.</p>
          <Link to="/login" className="btn btn-primary btn-lg"><Icon name="unlocked" size={16} />Sign in to Axon</Link>
        </motion.section>

        <footer className="lp-foot">
          <span>© Axon · Built on 100% synthetic data</span>
          <span>No real patient, member, provider or payer data is used.</span>
        </footer>
      </div>
    </div>
  );
}

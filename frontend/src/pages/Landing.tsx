import { motion } from 'motion/react';
import { Link } from 'react-router-dom';
import { NumberTicker } from '../components/fx';
import { Globe } from '../components/Globe';

const fmtCount = (n: number) => num(Math.round(n));
import { Icon } from '../components/Icon';
import { MascotMark } from '../components/Mascot';
import { Skeleton } from '../components/ui';
import { api } from '../lib/api';
import { inr, num } from '../lib/format';
import { useAsync } from '../lib/hooks';


const rise = { initial: { opacity: 0, y: 16 }, whileInView: { opacity: 1, y: 0 }, viewport: { once: true, margin: '-60px' }, transition: { duration: .5, ease: [.22, 1, .36, 1] as const } };

export function Landing() {
  const ov = useAsync(() => api.overview(), []);
  const q = useAsync(() => api.queue(40, 30), []);

  const f = ov.data?.funnel;
  const atStake = q.data?.cases.reduce((s, c) => s + c.dollars_at_risk, 0);
  const holdable = q.data?.cases.filter(c => c.hold_recommended).length;
  // The funnel, as the engine reports it: everything read, down to what a person looks at today.
  const stats = f ? [
    { v: f.claim_lines, l: 'claim lines read' },
    { v: f.alerts, l: 'alerts raised' },
    { v: f.explained, l: 'explained away' },
    { v: f.cases, l: 'cases built' },
    { v: f.selected_today, l: `picked for today’s ${f.capacity_hours} review hours` },
  ] : [];

  return (
    <div className="landing">
      <header className="landing-nav container">
        <Link to="/" className="brand landing-brand"><MascotMark size={38} />Axon</Link>
      </header>

      <section className="landing-hero container">
        <motion.div className="hero-copy" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .6, ease: [.22, 1, .36, 1] }}>
          <h1 className="hero-title">ClaimShield <span className="text-sheen">Nexus</span></h1>
          <p className="hero-sub">A unified platform that identifies suspicious claims and coordinated networks, predicts future risk, explains the evidence, and prioritizes cases for Special Investigations Unit review.</p>
          <div className="row-flex" style={{ gap: 10, marginTop: 26 }}>
            <Link to="/home" className="btn btn-primary btn-md btn-shimmer">Dive in<Icon name="arrow-right" size={15} /></Link>
          </div>
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
                    <b><NumberTicker value={s.v} format={fmtCount} /></b><span>{s.l}</span>
                  </div>
                ))}
              </div>
            </>
          ) : <Skeleton h={88} />}
        </motion.div>
      </section>

    </div>
  );
}

import { motion, useScroll, useSpring, useTransform, type MotionValue } from 'motion/react';
import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { Link } from 'react-router-dom';
import { Globe } from '../components/Globe';
import { Icon, type IconName } from '../components/Icon';
import { MascotMark } from '../components/Mascot';
import { LoginForm } from './Login';
import './landing.css';

const chips: { icon: IconName; big: string; small: string; at: number; pos: CSSProperties }[] = [
  { icon: 'status-critical', big: '₹5.34L', small: 'held before release', at: .26, pos: { top: '22%', left: '6%' } },
  { icon: 'org-chart', big: '47 connected claims', small: '3 providers, 1 owner', at: .34, pos: { top: '30%', right: '5%' } },
  { icon: 'accept', big: '27 alerts', small: 'explained away first', at: .42, pos: { bottom: '18%', left: '9%' } },
];
const steps = ['Detect with 4 methods', 'Explain the innocent away', 'Rank by recovery per hour', 'A human decides'];

function useNarrow() {
  const [n, setN] = useState(() => window.innerWidth < 860);
  useEffect(() => { const f = () => setN(window.innerWidth < 860); window.addEventListener('resize', f); return () => window.removeEventListener('resize', f); }, []);
  return n;
}

/** A window [a,b] that fades in, holds, then fades out (or holds to the end if `stay`). */
const useWin = (p: MotionValue<number>, a: number, b: number, stay = false) =>
  useTransform(p, stay ? [a, a + .05] : [a, a + .05, b - .05, b], stay ? [0, 1] : [0, 1, 1, 0]);

function Chip({ p, c }: { p: MotionValue<number>; c: typeof chips[number] }) {
  const o = useWin(p, c.at, .62);
  const y = useTransform(p, [c.at, c.at + .08], [24, 0]);
  return (
    <motion.div className="lp-float gl-chip" style={{ ...c.pos, opacity: o, y }}>
      <Icon name={c.icon} size={18} /><span><b>{c.big}</b><span className="muted">{c.small}</span></span>
    </motion.div>
  );
}

export function Landing() {
  const ref = useRef<HTMLDivElement>(null);
  const narrow = useNarrow();
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end end'] });
  const p = useSpring(scrollYProgress, { stiffness: 90, damping: 24, mass: .4 });

  // Act 1 (0–.2): the "Axon" title over a half-risen globe.
  const titleO = useTransform(p, [0, .14, .22], [1, 1, 0]);
  const titleY = useTransform(p, [0, .22], [0, -120]);
  const titleS = useTransform(p, [0, .22], [1, .9]);
  // Globe path: rises from the fold, sits centered, then glides aside for sign-in.
  const gY = useTransform(p, [0, .25, .78, 1], narrow ? ['38vh', '4vh', '4vh', '-30vh'] : ['44vh', '4vh', '4vh', '2vh']);
  const gX = useTransform(p, [.78, 1], ['0vw', narrow ? '0vw' : '-22vw']);
  const gS = useTransform(p, [0, .25, .55, .78, 1], narrow ? [1, 1, 1.08, 1, .5] : [1, .95, 1.06, 1, .86]);
  // Act 3 (.5–.8): the thesis.
  const thesisO = useWin(p, .52, .8);
  const thesisY = useTransform(p, [.52, .6], [30, 0]);
  // Act 4 (.82–1): sign-in.
  const cardO = useTransform(p, [.82, .94], [0, 1]);
  const cardX = useTransform(p, [.8, .97], narrow ? ['0vw', '0vw'] : ['30vw', '0vw']);
  const cardY = useTransform(p, [.8, .97], narrow ? ['60vh', '0vh'] : ['0vh', '0vh']);
  const cardPE = useTransform(p, v => (v > .9 ? 'auto' : 'none'));
  const hintO = useTransform(p, [0, .06], [1, 0]);
  const bar = useTransform(p, [0, 1], ['0%', '100%']);

  const toLogin = () => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' });

  return (
    <div className="gl" ref={ref}>
      <motion.div className="gl-bar" style={{ width: bar }} />
      <header className="gl-nav container">
        <Link to="/welcome" className="brand" aria-label="Axon"><MascotMark size={30} />Axon</Link>
        <nav className="row-flex" style={{ gap: 8 }}>
          <Link to="/" className="btn btn-ghost btn-sm hide-sm">Explore demo</Link>
          <button className="btn btn-primary btn-sm" onClick={toLogin}>Sign in</button>
        </nav>
      </header>

      <div className="gl-stage">
        <div className="gl-aura" />

        <motion.div className="gl-hero" style={{ opacity: titleO, y: titleY, scale: titleS }}>
          <span className="lp-tag"><span className="dot" />Fraud, waste &amp; abuse intelligence</span>
          <h1 className="gl-title">Axon</h1>
          <p className="gl-sub">Connected claims tell the truth.</p>
        </motion.div>

        <motion.div className="gl-globe" style={{ x: gX, y: gY, scale: gS }}>
          <Globe progress={p} />
        </motion.div>

        {chips.map(c => <Chip key={c.big} p={p} c={c} />)}

        <motion.div className="gl-thesis" style={{ opacity: thesisO, y: thesisY }}>
          <div className="eyebrow">One claim looks normal</div>
          <h2>Forty-seven connected claims <em>don’t.</em></h2>
          <div className="gl-steps">
            {steps.map((s, i) => <span key={s}><b>{i + 1}</b>{s}</span>)}
          </div>
        </motion.div>

        <motion.div className="gl-card card" style={{ opacity: cardO, x: cardX, y: cardY, pointerEvents: cardPE }}>
          <LoginForm back={false} />
        </motion.div>

        <motion.div className="gl-hint" style={{ opacity: hintO }}>
          <span>Scroll to explore</span><motion.i animate={{ y: [0, 6, 0] }} transition={{ duration: 1.6, repeat: Infinity }} />
        </motion.div>
      </div>
    </div>
  );
}

import { motion } from 'motion/react';
import { useEffect, useState } from 'react';

/**
 * Argus, the Axon owl.
 * Built from a handful of simple shapes and two colours taken from the accent:
 * ear tufts, a round body, big patient eyes (it watches, it doesn't judge),
 * and the axon network on its chest: three connected dots, like linked claims.
 */
export type MascotMood = 'watching' | 'thinking' | 'happy' | 'rest';

export function Mascot({ size = 110, mood = 'watching', title = 'Argus the owl' }: { size?: number; mood?: MascotMood; title?: string }) {
  const [blink, setBlink] = useState(false);
  useEffect(() => {
    if (mood !== 'watching' && mood !== 'thinking') return;
    const t = setInterval(() => { setBlink(true); setTimeout(() => setBlink(false), 140); }, 4200);
    return () => clearInterval(t);
  }, [mood]);
  const look = mood === 'thinking' ? { x: -3, y: -3 } : { x: 0, y: 1 };
  const closed = blink || mood === 'rest';

  return (
    <svg viewBox="0 0 160 150" width={size} height={size * 0.94} className="mascot" role="img" aria-label={title}>
      <motion.g animate={mood === 'happy' ? { y: [0, -7, 0] } : { y: [0, -2, 0] }}
        transition={{ duration: mood === 'happy' ? 0.6 : 3.4, repeat: Infinity, repeatDelay: mood === 'happy' ? 1.2 : 0, ease: 'easeInOut' }}>
        {/* feet */}
        <rect x="56" y="128" width="18" height="12" rx="6" className="m-light" />
        <rect x="86" y="128" width="18" height="12" rx="6" className="m-light" />
        {/* ear tufts */}
        <path d="M40 44 L22 10 L66 30 Z" className="m-dark" />
        <path d="M120 44 L138 10 L94 30 Z" className="m-dark" />
        {/* body */}
        <rect x="30" y="24" width="100" height="110" rx="48" className="m-dark" />
        {/* chest with the axon network */}
        <ellipse cx="80" cy="110" rx="30" ry="22" className="m-light" />
        <path d="M67 114 L80 100 L93 116" className="m-net" style={{ stroke: 'var(--m-dark)', opacity: .55 }} />
        <circle cx="67" cy="114" r="4.5" className="m-dark" style={{ opacity: .7 }} />
        <circle cx="80" cy="100" r="4.5" className="m-dark" style={{ opacity: .7 }} />
        <circle cx="93" cy="116" r="4.5" className="m-dark" style={{ opacity: .7 }} />
        {/* face discs */}
        <circle cx="58" cy="60" r="21" className="m-light" />
        <circle cx="102" cy="60" r="21" className="m-light" />
        {/* eyes */}
        {closed ? (
          <>
            <path d="M48 60 q10 6 20 0" className="m-line" />
            <path d="M92 60 q10 6 20 0" className="m-line" />
          </>
        ) : mood === 'happy' ? (
          <>
            <path d="M48 63 q10 -11 20 0" className="m-line" />
            <path d="M92 63 q10 -11 20 0" className="m-line" />
          </>
        ) : (
          <>
            <circle cx="58" cy="60" r="14" className="m-white" />
            <circle cx="102" cy="60" r="14" className="m-white" />
            <circle cx={58 + look.x} cy={60 + look.y} r="6.5" className="m-dark" />
            <circle cx={102 + look.x} cy={60 + look.y} r="6.5" className="m-dark" />
          </>
        )}
        {/* beak */}
        <path d="M73 76 L87 76 L80 88 Z" className="m-dark" />
      </motion.g>
      {mood === 'thinking' && [0, 1, 2].map(i => (
        <motion.circle key={i} cx={136 + i * 8} cy={30 - i * 8} r={3 + i} className="m-dark"
          animate={{ opacity: [0.2, 1, 0.2] }} transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }} />
      ))}
    </svg>
  );
}

/** Small owl-face mark for the top bar and favicon-sized spots. */
export function MascotMark({ size = 30 }: { size?: number }) {
  return (
    <svg viewBox="0 0 40 40" width={size} height={size} aria-hidden>
      <rect width="40" height="40" rx="11" className="m-bg" />
      <path d="M9 14 L11 6 L16 11 Z M31 14 L29 6 L24 11 Z" fill="#fff" opacity=".9" />
      <rect x="8" y="9" width="24" height="25" rx="11" fill="#fff" opacity=".92" />
      <circle cx="15" cy="19" r="3" className="m-bg" />
      <circle cx="25" cy="19" r="3" className="m-bg" />
      <path d="M15 29 L20 25 L25 29" fill="none" stroke="var(--m-light)" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

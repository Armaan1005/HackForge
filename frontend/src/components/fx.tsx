// Small motion touches borrowed from Magic UI / Eldora UI patterns. Each respects prefers-reduced-motion.
import { useInView } from 'motion/react';
import { useEffect, useRef } from 'react';

const reduced = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Magic UI "Number Ticker": counts up to `value` (ease-out, ~1.2 s) the first time it scrolls into view,
 *  and always finishes on the exactly formatted value. */
export function NumberTicker({ value, format, duration = 1200 }: { value: number; format: (n: number) => string; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: '-30px' });
  const shown = useRef(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reduced() || document.hidden) { el.textContent = format(value); shown.current = value; return; }
    if (!inView) return;
    const from = shown.current, t0 = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / duration), e = 1 - (1 - p) ** 3;
      shown.current = from + (value - from) * e;
      el.textContent = format(p < 1 ? shown.current : value);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    // if the tab is backgrounded mid-count, land on the final value anyway
    const done = setTimeout(() => { el.textContent = format(value); shown.current = value; }, duration + 400);
    return () => { cancelAnimationFrame(raf); clearTimeout(done); };
  }, [inView, value]); // eslint-disable-line react-hooks/exhaustive-deps
  return <span ref={ref} style={{ fontVariantNumeric: 'tabular-nums' }}>{format(0)}</span>;
}

/** Magic UI "Border Beam": a light that travels round the edge of its (position: relative) parent. */
export function BorderBeam() {
  return <span className="border-beam" aria-hidden />;
}

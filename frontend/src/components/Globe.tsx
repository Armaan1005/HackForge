import createGlobe from 'cobe';
import { useEffect, useRef } from 'react';
import type { MotionValue } from 'motion/react';

/** Synthetic-data cities Axon watches (same as the engine's geo table). */
const CITIES: [number, number, number][] = [
  [19.08, 72.88, .09], [18.52, 73.86, .06], [28.61, 77.21, .1], [12.97, 77.59, .08], [13.08, 80.27, .07],
  [26.85, 80.95, .06], [23.02, 72.57, .06], [26.45, 80.33, .05], [21.15, 79.09, .05], [21.17, 72.83, .05],
  [25.32, 82.97, .04], [11.02, 76.96, .04], [9.93, 78.12, .04], [27.57, 81.6, .04], [22.84, 74.26, .04],
];
const FOCUS_PHI = Math.PI - (78 * Math.PI / 180 - Math.PI / 2); // India, longitude ~78°E
const smooth = (x: number) => x * x * (3 - 2 * x);

/** Light dotted cobe globe whose spin follows `progress` (0..1) and lands on India at 1. */
export function Globe({ progress, className }: { progress: MotionValue<number>; className?: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let w = el.offsetWidth, phi = FOCUS_PHI - 7.85, theta = .15, t = 0;
    const onResize = () => { w = el.offsetWidth; };
    window.addEventListener('resize', onResize);
    const globe = createGlobe(el, {
      devicePixelRatio: 2, width: w * 2, height: w * 2, phi, theta, dark: 0, diffuse: .5,
      mapSamples: 16000, mapBrightness: 1.25, mapBaseBrightness: .02,
      baseColor: [1, 1, 1], markerColor: [.16, .48, .36], glowColor: [.93, .95, .92], opacity: .92,
      markers: CITIES.map(([lat, lon, size]) => ({ location: [lat, lon], size })),
      onRender: state => {
        const p = Math.min(1, Math.max(0, progress.get()));
        if (!reduce) t += .004;
        const target = FOCUS_PHI - (1 - p) * 7.85 + t * (1 - smooth(p));
        phi += (target - phi) * .08;
        theta += ((.15 + .2 * smooth(p)) - theta) * .08;
        state.phi = phi; state.theta = theta;
        state.width = w * 2; state.height = w * 2;
        const pulse = 1 + .35 * Math.sin(t * 6) * smooth(p);
        state.markers = CITIES.map(([lat, lon, size]) => ({ location: [lat, lon], size: size * pulse }));
      },
    });
    requestAnimationFrame(() => { el.style.opacity = '1'; });
    return () => { globe.destroy(); window.removeEventListener('resize', onResize); };
  }, [progress]);

  return <canvas ref={canvas} className={className} style={{ width: '100%', aspectRatio: '1', opacity: 0, transition: 'opacity 1.2s ease', contain: 'layout paint size' }} />;
}

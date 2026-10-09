// Port of Magic UI's <Globe /> (magicui.design/docs/components/globe): cobe + a motion spring for drag.
// Same behaviour (slow spin, drag to rotate with momentum), restyled with Axon's palette and centred on India,
// where the synthetic data is set.
import createGlobe, { type COBEOptions } from 'cobe';
import { useMotionValue, useSpring } from 'motion/react';
import { useEffect, useRef } from 'react';

const MOVEMENT_DAMPING = 1400;
const toAngles = (lat: number, lng: number): [number, number] => [Math.PI - ((lng * Math.PI) / 180 - Math.PI / 2), (lat * Math.PI) / 180];
const [PHI0] = toAngles(21, 78);

// Simplified outline of India (lat, lng). A grid of small dots inside it makes the country stand out on the globe.
const INDIA: [number, number][] = [
  [35.5, 74.5], [34.6, 78.2], [32.6, 79.4], [30.6, 81.1], [28.6, 84.2], [27.4, 88.1], [28.0, 88.8], [28.2, 92.0], [27.8, 95.6], [26.9, 97.1],
  [25.2, 95.0], [23.5, 94.0], [22.0, 92.6], [23.6, 91.6], [24.3, 89.8], [22.2, 89.0], [21.6, 87.2], [19.6, 85.2], [17.6, 83.2], [15.8, 81.0],
  [13.5, 80.3], [10.4, 79.9], [8.1, 77.5], [8.6, 76.7], [11.5, 75.6], [14.6, 74.3], [17.0, 73.3], [19.0, 72.8], [20.8, 72.7], [22.3, 70.8],
  [22.8, 68.8], [24.3, 68.8], [24.8, 71.0], [26.6, 70.1], [28.1, 71.6], [30.1, 73.4], [32.5, 74.7], [34.1, 73.9],
];
const inside = (lat: number, lng: number) => {
  let hit = false;
  for (let i = 0, j = INDIA.length - 1; i < INDIA.length; j = i++) {
    const [ay, ax] = INDIA[i], [by, bx] = INDIA[j];
    if ((ay > lat) !== (by > lat) && lng < ((bx - ax) * (lat - ay)) / (by - ay) + ax) hit = !hit;
  }
  return hit;
};
const INDIA_DOTS: { location: [number, number]; size: number }[] = [];
// cobe draws at most 64 markers (its shader has 64 slots); a sparse 3.5° grid keeps India visible without crowding the cities.
for (let lat = 9; lat <= 36; lat += 3.5) for (let lng = 70; lng <= 97.5; lng += 3.5) if (inside(lat, lng)) INDIA_DOTS.push({ location: [lat, lng], size: 0.04 });

export const GLOBE_CONFIG: COBEOptions = {
  width: 800, height: 800, onRender: () => {}, devicePixelRatio: 2,
  phi: PHI0, theta: 0.32, dark: 1, diffuse: 1.2, mapSamples: 16000, mapBrightness: 6,  // dark globe, as in Eldora UI's Cobe Globe
  baseColor: [0.3, 0.3, 0.3],
  markerColor: [0.3, 0.85, 0.6],                    // brighter green so India reads on black
  glowColor: [0.85, 0.85, 0.82],
  markers: [
    ...INDIA_DOTS,
    { location: [19.076, 72.8777], size: 0.06 },   // Mumbai
    { location: [28.6139, 77.209], size: 0.055 },   // Delhi
    { location: [12.9716, 77.5946], size: 0.04 },  // Bengaluru
    { location: [13.0827, 80.2707], size: 0.035 },  // Chennai
    { location: [17.385, 78.4867], size: 0.035 },   // Hyderabad
    { location: [22.5726, 88.3639], size: 0.035 },  // Kolkata
    { location: [18.5204, 73.8567], size: 0.03 },  // Pune
    { location: [23.0225, 72.5714], size: 0.03 },  // Ahmedabad
    { location: [26.9124, 75.7873], size: 0.025 },  // Jaipur
    { location: [26.8467, 80.9462], size: 0.025 },  // Lucknow
  ],
};

export function Globe({ className = '', config = GLOBE_CONFIG }: { className?: string; config?: COBEOptions }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pointerInteracting = useRef<number | null>(null);
  const r = useMotionValue(0);
  const rs = useSpring(r, { mass: 1, damping: 30, stiffness: 100 });

  const setPointer = (value: number | null) => {
    pointerInteracting.current = value;
    if (canvasRef.current) canvasRef.current.style.cursor = value !== null ? 'grabbing' : 'grab';
  };
  const move = (clientX: number) => {
    if (pointerInteracting.current === null) return;
    const delta = clientX - pointerInteracting.current;
    pointerInteracting.current = clientX;
    r.set(r.get() + delta / (MOVEMENT_DAMPING / 10));
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let phi = config.phi ?? 0;
    let width = canvas.offsetWidth;
    const onResize = () => { width = canvas.offsetWidth; };
    window.addEventListener('resize', onResize);
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const globe = createGlobe(canvas, {
      ...config, markers: (config.markers ?? []).slice(-64), width: width * 2, height: width * 2,
      onRender: state => {
        if (pointerInteracting.current === null && !still) phi += 0.003;
        state.phi = phi + rs.get();
        state.width = width * 2;
        state.height = width * 2;
      },
    });
    const t = setTimeout(() => { canvas.style.opacity = '1'; });
    return () => { clearTimeout(t); globe.destroy(); window.removeEventListener('resize', onResize); };
  }, [rs, config]);

  return (
    <div className={`globe ${className}`}>
      <canvas ref={canvasRef} aria-label="Globe centred on India"
        onPointerDown={e => setPointer(e.clientX)} onPointerUp={() => setPointer(null)} onPointerOut={() => setPointer(null)}
        onMouseMove={e => move(e.clientX)} onTouchMove={e => e.touches[0] && move(e.touches[0].clientX)} />
    </div>
  );
}

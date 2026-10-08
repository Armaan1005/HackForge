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
// cobe draws at most 64 markers (its shader has 64 slots): a 2.5° grid gives 46 dots, leaving room for the 10 cities.
for (let lat = 8.2; lat <= 36; lat += 2.5) for (let lng = 68.5; lng <= 97.5; lng += 2.5) if (inside(lat, lng)) INDIA_DOTS.push({ location: [lat, lng], size: 0.04 });

// India's border (lat, lng), clockwise from the north-west, following the official map.
const BORDER: [number, number][] = [
  [35.1, 72.9], [36.9, 74.7], [37.1, 75.6], [36.0, 77.8], [35.5, 80.2], [34.8, 79.6], [33.2, 79.4], [32.4, 79.3], [31.3, 79.0], [30.9, 80.2],
  [30.2, 81.0], [28.8, 80.3], [28.4, 81.3], [27.6, 83.3], [27.4, 84.6], [26.6, 86.0], [26.4, 87.4], [26.4, 88.1], [27.8, 88.1], [28.1, 88.9],
  [27.2, 89.0], [26.8, 89.8], [26.9, 92.1], [27.8, 92.0], [28.2, 93.0], [29.3, 94.6], [28.6, 96.4], [27.8, 97.1], [27.1, 96.2], [26.2, 95.2],
  [25.1, 94.6], [24.0, 94.2], [23.2, 93.4], [22.0, 93.0], [22.0, 92.5], [23.6, 91.9], [24.1, 92.2], [24.9, 92.4], [25.2, 91.0], [25.2, 89.9],
  [26.1, 89.8], [26.0, 88.6], [25.2, 88.4], [24.6, 88.0], [24.0, 88.6], [22.9, 88.9], [21.6, 88.9], [21.5, 87.4], [20.7, 86.9], [19.9, 86.0],
  [19.2, 84.8], [18.2, 83.9], [17.0, 82.3], [16.3, 81.3], [15.8, 80.3], [14.5, 80.1], [13.4, 80.3], [12.0, 79.9], [10.8, 79.8], [10.3, 79.3],
  [9.3, 79.0], [8.1, 77.5], [8.6, 76.8], [10.0, 76.2], [11.4, 75.7], [12.8, 74.9], [14.6, 74.2], [15.8, 73.6], [17.5, 73.1], [19.0, 72.8],
  [20.4, 72.8], [21.2, 72.6], [22.2, 72.5], [21.6, 72.2], [20.9, 71.0], [21.0, 70.0], [21.8, 69.2], [22.4, 69.3], [22.8, 70.4], [23.0, 68.4],
  [23.6, 68.2], [24.3, 68.8], [24.4, 71.0], [25.2, 70.6], [25.7, 70.2], [26.5, 70.1], [27.6, 70.6], [28.0, 71.9], [29.0, 73.0], [30.0, 73.4],
  [31.0, 74.6], [32.1, 74.7], [32.8, 74.0], [33.8, 74.0], [34.3, 73.5],
];
// Same maths as cobe's shader: unit-sphere point from lat/lng, rotated by J(theta, phi), sphere drawn at 0.8 of the canvas.
function project(lat: number, lng: number, phi: number, theta: number, size: number): [number, number] | null {
  const t = (lat * Math.PI) / 180, n = (lng * Math.PI) / 180 - Math.PI;
  const p0 = -Math.cos(t) * Math.cos(n), p1 = Math.sin(t), p2 = Math.cos(t) * Math.sin(n);
  const c = Math.cos(theta), d = Math.cos(phi), e = Math.sin(theta), f = Math.sin(phi);
  const lx = d * p0 + f * p2, ly = f * e * p0 + c * p1 - d * e * p2, lz = -f * c * p0 + e * p1 + d * c * p2;
  if (lz < 0.02) return null;  // behind the globe
  return [((0.8 * lx + 1) / 2) * size, ((1 - 0.8 * ly) / 2) * size];
}
function borderPath(phi: number, theta: number, size: number) {
  let d = '', pen = false;
  for (let i = 0; i <= BORDER.length; i++) {
    const [a, b] = BORDER[i % BORDER.length], [pa, pb] = BORDER[(i + BORDER.length - 1) % BORDER.length];
    for (let k = i === 0 ? 3 : 1; k <= 3; k++) {  // 3 steps per edge so lines follow the curve of the globe
      const q = project(pa + ((a - pa) * k) / 3, pb + ((b - pb) * k) / 3, phi, theta, size);
      if (!q) { pen = false; continue; }
      d += `${pen ? 'L' : 'M'}${q[0].toFixed(1)} ${q[1].toFixed(1)}`;
      pen = true;
    }
  }
  return d;
}

export const GLOBE_CONFIG: COBEOptions = {
  width: 800, height: 800, onRender: () => {}, devicePixelRatio: 2,
  phi: PHI0, theta: 0.32, dark: 0, diffuse: 0.4, mapSamples: 16000, mapBrightness: 1.2,
  baseColor: [1, 1, 1],
  markerColor: [43 / 255, 138 / 255, 99 / 255],   // --series-1
  glowColor: [0.96, 0.96, 0.94],
  markers: [
    ...INDIA_DOTS,
    { location: [19.076, 72.8777], size: 0.12 },   // Mumbai
    { location: [28.6139, 77.209], size: 0.11 },   // Delhi
    { location: [12.9716, 77.5946], size: 0.08 },  // Bengaluru
    { location: [13.0827, 80.2707], size: 0.07 },  // Chennai
    { location: [17.385, 78.4867], size: 0.07 },   // Hyderabad
    { location: [22.5726, 88.3639], size: 0.07 },  // Kolkata
    { location: [18.5204, 73.8567], size: 0.06 },  // Pune
    { location: [23.0225, 72.5714], size: 0.06 },  // Ahmedabad
    { location: [26.9124, 75.7873], size: 0.05 },  // Jaipur
    { location: [26.8467, 80.9462], size: 0.05 },  // Lucknow
  ],
};

export function Globe({ className = '', config = GLOBE_CONFIG }: { className?: string; config?: COBEOptions }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const borderRef = useRef<SVGPathElement>(null);
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
        if (borderRef.current && svgRef.current) {
          svgRef.current.setAttribute('viewBox', `0 0 ${width} ${width}`);
          borderRef.current.setAttribute('d', borderPath(state.phi, config.theta ?? 0, width));
        }
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
      <svg ref={svgRef} className="globe-border" aria-hidden><path ref={borderRef} /></svg>
    </div>
  );
}

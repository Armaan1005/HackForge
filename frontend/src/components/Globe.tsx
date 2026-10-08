// Wireframe dotted globe (after 21st.dev "Wireframe Dotted Globe"), redrawn for Axon's light theme with d3-geo.
// One orthographic projection draws everything (graticule, coastline, land dots, India), so India's border sits
// exactly on the map and is clipped cleanly at the horizon. Drag to rotate; it spins slowly on its own.
import { geoContains, geoDistance, geoGraticule10, geoOrthographic, geoPath } from 'd3-geo';
import type { Feature, FeatureCollection, MultiPolygon, Polygon } from 'geojson';
import { useEffect, useRef } from 'react';
import { feature } from 'topojson-client';
import type { GeometryCollection, Topology } from 'topojson-specification';
import landTopo from 'world-atlas/land-110m.json';

// India's border as on the official map (lat, lng), clockwise from the north-west.
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
const CITIES: [number, number][] = [[72.88, 19.08], [77.21, 28.61], [77.59, 12.97], [80.27, 13.08], [78.49, 17.39], [88.36, 22.57]];

// d3 wants [lng, lat] and a clockwise exterior ring; reverse if the ring came out as "everything but India".
const ring = BORDER.map(([lat, lng]) => [lng, lat] as [number, number]);
ring.push(ring[0]);
const INDIA: Feature<Polygon> = { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [ring] } };
if (geoContains(INDIA, [0, 0])) ring.reverse();

const LAND = feature(landTopo as unknown as Topology, (landTopo as unknown as Topology<{ land: GeometryCollection }>).objects.land) as unknown as
  FeatureCollection<MultiPolygon | Polygon>;

/** Evenly spaced points on land (closer in longitude near the poles so spacing stays even), plus a denser set for India. */
function sampleDots() {
  const land: [number, number][] = [], india: [number, number][] = [];
  for (let lat = -56; lat <= 78; lat += 2.2) {
    const step = 2.2 / Math.max(0.2, Math.cos((lat * Math.PI) / 180));
    for (let lng = -180; lng < 180; lng += step) {
      const p: [number, number] = [lng, lat];
      if (geoContains(INDIA, p)) continue;
      if (geoContains(LAND, p)) land.push(p);
    }
  }
  for (let lat = 7; lat <= 37.5; lat += 1.1) for (let lng = 68; lng <= 97.5; lng += 1.1) if (geoContains(INDIA, [lng, lat])) india.push([lng, lat]);
  return { land, india };
}

export function Globe({ className = '' }: { className?: string }) {
  const box = useRef<HTMLDivElement>(null);
  const cv = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = cv.current!, el = box.current!;
    const ctx = canvas.getContext('2d')!;
    const accent = getComputedStyle(document.documentElement).getPropertyValue('--series-1').trim() || '#2b8a63';
    const { land, india } = sampleDots();
    const graticule = geoGraticule10();
    const proj = geoOrthographic().clipAngle(90).rotate([-78, -18, 0]).precision(0.5);
    const path = geoPath(proj, ctx);
    let size = 0, rot: [number, number] = [-78, -18], drag: { x: number; y: number; r: [number, number] } | null = null;
    let raf = 0, visible = true, t = 0;
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const resize = () => {
      size = el.clientWidth;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = canvas.height = Math.round(size * dpr);
      canvas.style.width = canvas.style.height = `${size}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      proj.translate([size / 2, size / 2]).scale(size * 0.42);
    };
    const dot = (p: [number, number], r: number, center: [number, number]) => {
      if (geoDistance(p, center) > Math.PI / 2 - 0.02) return;
      const [x, y] = proj(p)!;
      ctx.moveTo(x + r, y);
      ctx.arc(x, y, r, 0, Math.PI * 2);
    };

    const draw = () => {
      if (!drag && !still) rot = [rot[0] + 0.12, rot[1]];
      proj.rotate([rot[0], rot[1], 0]);
      const center: [number, number] = [-rot[0], -rot[1]];
      const R = proj.scale(), c = size / 2;
      ctx.clearRect(0, 0, size, size);

      // sphere: soft white body with a faint rim
      const g = ctx.createRadialGradient(c - R * 0.35, c - R * 0.35, R * 0.1, c, c, R);
      g.addColorStop(0, '#ffffff'); g.addColorStop(1, '#efefea');
      ctx.beginPath(); path({ type: 'Sphere' }); ctx.fillStyle = g; ctx.fill();
      ctx.lineWidth = 1; ctx.strokeStyle = 'rgba(20,20,30,.16)'; ctx.stroke();

      // wireframe
      ctx.beginPath(); path(graticule); ctx.lineWidth = 0.6; ctx.strokeStyle = 'rgba(20,20,30,.07)'; ctx.stroke();
      // coastline
      ctx.beginPath(); path(LAND); ctx.lineWidth = 0.7; ctx.strokeStyle = 'rgba(20,20,30,.18)'; ctx.stroke();
      // land dots
      ctx.beginPath(); for (const p of land) dot(p, 0.95, center); ctx.fillStyle = 'rgba(20,20,30,.38)'; ctx.fill();

      // India: tinted fill, green dots, crisp border
      ctx.beginPath(); path(INDIA); ctx.fillStyle = 'rgba(43,138,99,.10)'; ctx.fill();
      ctx.beginPath(); for (const p of india) dot(p, 1.25, center); ctx.fillStyle = accent; ctx.fill();
      ctx.beginPath(); path(INDIA); ctx.lineWidth = 1.4; ctx.lineJoin = 'round'; ctx.strokeStyle = accent; ctx.stroke();

      // cities, with a slow pulse
      t += 0.02;
      for (const [i, p] of CITIES.entries()) {
        if (geoDistance(p, center) > Math.PI / 2 - 0.05) continue;
        const [x, y] = proj(p)!, k = (Math.sin(t + i) + 1) / 2;
        ctx.beginPath(); ctx.arc(x, y, 3 + k * 5, 0, Math.PI * 2); ctx.fillStyle = `rgba(43,138,99,${0.22 * (1 - k)})`; ctx.fill();
        ctx.beginPath(); ctx.arc(x, y, 2.6, 0, Math.PI * 2); ctx.fillStyle = accent; ctx.fill();
        ctx.lineWidth = 1.2; ctx.strokeStyle = '#fff'; ctx.stroke();
      }
      raf = visible ? requestAnimationFrame(draw) : 0;
    };

    const down = (e: PointerEvent) => { drag = { x: e.clientX, y: e.clientY, r: rot }; canvas.setPointerCapture(e.pointerId); canvas.style.cursor = 'grabbing'; };
    const move = (e: PointerEvent) => {
      if (!drag) return;
      const k = 180 / (proj.scale() * Math.PI);
      rot = [drag.r[0] + (e.clientX - drag.x) * k, Math.max(-60, Math.min(60, drag.r[1] - (e.clientY - drag.y) * k))];
    };
    const up = () => { drag = null; canvas.style.cursor = 'grab'; };
    canvas.addEventListener('pointerdown', down);
    canvas.addEventListener('pointermove', move);
    canvas.addEventListener('pointerup', up);
    canvas.addEventListener('pointercancel', up);

    const ro = new ResizeObserver(resize);
    ro.observe(el);
    const io = new IntersectionObserver(([en]) => { visible = en.isIntersecting; if (visible && !raf) raf = requestAnimationFrame(draw); });
    io.observe(el);
    resize();
    draw();  // paint the first frame now; draw() keeps itself going with requestAnimationFrame
    canvas.style.opacity = '1';
    return () => {
      cancelAnimationFrame(raf); ro.disconnect(); io.disconnect();
      canvas.removeEventListener('pointerdown', down); canvas.removeEventListener('pointermove', move);
      canvas.removeEventListener('pointerup', up); canvas.removeEventListener('pointercancel', up);
    };
  }, []);

  return (
    <div ref={box} className={`globe ${className}`}>
      <canvas ref={cv} aria-label="Globe with India highlighted" style={{ touchAction: 'none' }} />
    </div>
  );
}

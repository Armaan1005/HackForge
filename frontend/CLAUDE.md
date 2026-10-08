# Part B: Axon UI

React 18 + TypeScript + Vite + `motion` + lucide icons + cytoscape. Plain CSS design tokens in `src/styles.css` (iOS-style: glass top nav with sliding pill, grouped cards, segmented controls, sheets). No Tailwind.

- Data: `src/lib/api.ts`. Engine calls (`api.*`) fall back to `contracts/*.json` when Part A's API isn't up; AI calls (`ai.*`) go to `/api/ai` and the UI shows template/offline states.
- Pages: Command (`/`), SIU Queue, Case (`/cases/:id` with Evidence · Network · Timeline · Documents · Evidence Court · Brief · Ask tabs), Explained, Fraud Twin, Trust, and `/challenge` (judge phone page, no nav).
- Charts are hand-rolled SVG in `components/charts.tsx` following the dataviz rules: reference palette via `--series-*`, status colours only with icon + label, legend for 2+ series, tooltips on every mark, real-pixel widths (`useWidth`).
- Never show a number the engine or verifier didn't produce. Status pills always pair colour with an icon and label.
- Typecheck: `npx tsc -b`. Dev: `npm run dev` (proxies `/api` to :8000).

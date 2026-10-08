# Part B: Axon UI

React 18 + TypeScript + Vite + `motion` + cytoscape. The design system is carried over from Armaan's Prism (SAP Hackathon) app: keep new UI consistent with it.

- **Tokens** (`src/styles.css`): warm off-white `--bg #f4f4f0`, white cards, calm green accent `hsl(158 34% 31%)`, radius 20px, line-height 1.6, soft shadows. Light only.
- **Icons**: SAP Horizon icons via `<Icon name="…" />` (`src/lib/icons.ts`, from `@ui5/webcomponents-icons`). Add a name there to use it. Don't add other icon libraries.
- **Mascot**: Argus the owl (`components/Mascot.tsx`, moods watching/thinking/happy/rest) in page headers, empty states and the Ask tab. `MascotMark` is the logo.
- **Patterns**: `PageHeader` (eyebrow + h1 + subtitle + mascot), `card-accent` "next step" cards, iOS grouped `Section` rows with `row-icon` tiles, `Status` (dot + text), `RiskPill`, `Strength`, `review-box` for human review, `help-panel`, `fair-note`/`Note`, `trace` steps, glass `toast()`.
- **Copy**: plain and human ("Good afternoon, Priya.", "Why it might be fine"). Explanations go in sheets, tooltips or `details`, not paragraphs.
- **Data**: `src/lib/api.ts`. Engine calls fall back to `contracts/*.json`; AI calls go to `/api/ai`.
- **Charts**: `components/charts.tsx`, validated palette (`--series-1` green, `--series-2` amber), tooltips on every mark, real-pixel widths.
- Typecheck: `npx tsc -b`. Dev: `npm run dev` (proxies `/api` to :8000).

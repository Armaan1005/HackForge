import { useSyncExternalStore } from 'react';
import { clone, fixtures } from './fixtures';
import { replanLocal } from './replan';
import type { AiStatus, CaseDetail, Court, Forensics, Graph, Queue, TimeMachine, TwinRun } from './types';

// ── data-source state (shown in the nav: Live engine vs Contract fixtures) ────
type Source = 'unknown' | 'live' | 'fixture';
let engineSource: Source = 'unknown';
const listeners = new Set<() => void>();
const setSource = (s: Source) => { if (s !== engineSource) { engineSource = s; listeners.forEach(l => l()); } };
export const useEngineSource = () => useSyncExternalStore(cb => { listeners.add(cb); return () => listeners.delete(cb); }, () => engineSource);

async function fetchJson<T>(path: string, init?: RequestInit, timeoutMs = 8000): Promise<T> {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetch(path, { ...init, signal: ctl.signal, headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) } });
    if (!r.ok) {
      let msg = `${r.status} ${r.statusText}`;
      try { const j = await r.json(); msg = j?.detail?.message || j?.error?.message || msg; } catch { /* not json */ }
      throw Object.assign(new Error(msg), { status: r.status });
    }
    return (await r.json()) as T;
  } finally { clearTimeout(t); }
}

/** Engine (Part A) call with contract-fixture fallback, so the UI works before the engine exists. */
async function engine<T>(path: string, fallback: () => T, init?: RequestInit): Promise<T> {
  try {
    const data = await fetchJson<T>(path, init);
    setSource('live');
    return data;
  } catch {
    setSource('fixture');
    return fallback();
  }
}

// ── local decision log (fixture mode only; live mode uses the engine's audit log) ──
export interface LocalDecision { decision_id: string; case_id: string; action: string; user: string; note: string; recorded_at: string }
const LOG_KEY = 'axon.decisions';
const readLog = (): LocalDecision[] => { try { return JSON.parse(localStorage.getItem(LOG_KEY) || '[]'); } catch { return []; } };
const writeLog = (l: LocalDecision[]) => { try { localStorage.setItem(LOG_KEY, JSON.stringify(l)); } catch { /* private mode */ } };
export const localDecisions = () => readLog();

// ── fixture helpers ──────────────────────────────────────────────────────────
const fixtureCase = (id: string): CaseDetail => {
  const c = clone(fixtures.caseDetail) as unknown as CaseDetail;
  if (id === c.case_id) return c;
  const row = (fixtures.queue.cases as unknown as Queue['cases']).find(x => x.case_id === id);
  if (!row) throw Object.assign(new Error(`Case ${id} not found`), { status: 404 });
  return {
    ...c, case_id: id, title: row.title, pattern: row.pattern, severity: row.severity, evidence_strength: row.evidence_strength,
    confidence: row.confidence, fixture_sample: true, scores: { ...c.scores, risk: row.risk },
    verdict: { ...c.verdict, status: row.status }, effort_hours: row.effort_hours, dead_end_risk: row.dead_end_risk,
    money: { ...c.money, dollars_at_risk: row.dollars_at_risk, expected_recovery: row.expected_recovery },
    payment_clock: { ...c.payment_clock, days_until_release: row.days_until_release, hold_recommended: row.hold_recommended },
    horizon_risk: row.horizon_risk,
  };
};

// ── Part A: engine ───────────────────────────────────────────────────────────
export const api = {
  overview: () => engine('/api/overview', () => clone(fixtures.overview)),
  queue: (capacity: number, horizon: number) =>
    engine<Queue>(`/api/queue?capacity_hours=${capacity}&horizon=${horizon}`, () => replanLocal(clone(fixtures.queue) as unknown as Queue, capacity, horizon)),
  case: async (id: string) => {
    try { const c = await fetchJson<CaseDetail>(`/api/cases/${id}`); setSource('live'); return c; }
    catch (e) { if ((e as { status?: number }).status === 404 && engineSource === 'live') throw e; setSource('fixture'); return fixtureCase(id); }
  },
  graph: (id: string) => engine<Graph>(`/api/cases/${id}/graph`, () => ({ ...(clone(fixtures.caseGraph) as unknown as Graph), case_id: id })),
  timemachine: (id: string) => engine<TimeMachine>(`/api/cases/${id}/timemachine`, () => ({ ...(clone(fixtures.timemachine) as unknown as TimeMachine), case_id: id })),
  forecast: (entity: string, horizon: number) => engine(`/api/forecast/${entity}?horizon=${horizon}`, () => {
    const f = clone(fixtures.forecast); const p = (f.all_horizons as Record<string, number>)[String(horizon)] ?? f.probability;
    return { ...f, entity_id: entity, horizon, probability: p, label_definition: f.label_definition.replace('30', String(horizon)) };
  }),
  cleared: (limit = 50) => engine(`/api/alerts/cleared?limit=${limit}`, () => clone(fixtures.alertsCleared)),
  trust: () => engine('/api/trust', () => clone(fixtures.trust)),
  audit: (limit = 50) => engine(`/api/audit?limit=${limit}`, () => clone(fixtures.audit)),
  twinScenarios: () => engine('/api/twin/scenarios', () => clone(fixtures.twinScenarios)),
  twinRun: (scenario: string, params: Record<string, unknown>, seed = 7) =>
    engine<TwinRun>('/api/twin/run', () => ({ ...(clone(fixtures.twinRun) as unknown as TwinRun), scenario, params, seed, run_id: `TWIN-FIXTURE-${Date.now() % 100000}` }),
      { method: 'POST', body: JSON.stringify({ scenario, params, seed }) }),
  twinHarden: (run_id: string, param: string, new_value: number) =>
    engine<TwinRun>('/api/twin/harden', () => {
      const h = clone(fixtures.twinHarden) as unknown as TwinRun;
      return { ...h, parent_run_id: run_id, change: { param, old_value: h.change?.old_value ?? 0, new_value } } as TwinRun;
    }, { method: 'POST', body: JSON.stringify({ run_id, change: { param, new_value } }) }),
  decision: (case_id: string, action: string, note: string, user = 'investigator') =>
    engine(`/api/cases/${case_id}/decision`, () => {
      const d: LocalDecision = { decision_id: `DEC-L${String(readLog().length + 1).padStart(3, '0')}`, case_id, action, user, note, recorded_at: new Date().toISOString().slice(0, 19) };
      writeLog([d, ...readLog()]);
      return { ...fixtures.decision.response, ...d, queue_changed: action === 'confirm' || action === 'clear', weight_changes: action === 'confirm' || action === 'clear' ? fixtures.decision.response.weight_changes : [], hold_status: action === 'hold_payment' ? 'held_by_human' : 'none', local: true };
    }, { method: 'POST', body: JSON.stringify({ action, user, note }) }),
};

// ── Part B: genai ────────────────────────────────────────────────────────────
export const ai = {
  status: () => fetchJson<AiStatus>('/api/ai/status', undefined, 4000),
  court: (id: string, refresh = false) => fetchJson<Court>(`/api/ai/court/${id}${refresh ? '?refresh=true' : ''}`, { method: 'POST' }, 90000),
  brief: (id: string) => fetchJson<{ markdown: string; source: string; note?: string }>(`/api/ai/brief/${id}`, undefined, 90000),
  forensics: (id: string) => fetchJson<Forensics>(`/api/ai/forensics/${id}`, { method: 'POST' }, 90000),
  explainCleared: (limit = 20) => fetchJson<{ items: { alert_id: string; text: string; source: string }[]; note?: string }>('/api/ai/explain_cleared', { method: 'POST', body: JSON.stringify({ limit }) }, 60000),
  twinParse: (text: string) => fetchJson<{ supported: boolean; scenario?: string; scenario_name?: string; params?: Record<string, unknown>; adjustments?: string[]; source: string; reason?: string }>('/api/ai/twin/parse', { method: 'POST', body: JSON.stringify({ text }) }, 45000),
  twinAdvise: (run: TwinRun) => fetchJson<{ suggested_change: { param: string; old_value: number; new_value: number } | null; explanation: string; source: string }>('/api/ai/twin/advise', { method: 'POST', body: JSON.stringify({ run }) }, 45000),
  ask: (id: string, question: string) => fetchJson<{ answer: string; evidence_ids: string[]; grounded: boolean; source: string }>(`/api/ai/ask/${id}`, { method: 'POST', body: JSON.stringify({ question }) }, 45000),
  trust: () => fetchJson<{ statements_checked: number; kept: number; uncited_blocked: number; numbers_blocked: number; model: string; enabled: boolean }>('/api/ai/trust', undefined, 4000),
  prewarm: () => fetchJson<{ queued_cases: string[] }>('/api/ai/prewarm', { method: 'POST' }),
};

export const briefDownloadUrl = (id: string) => `/api/ai/brief/${id}?format=md`;

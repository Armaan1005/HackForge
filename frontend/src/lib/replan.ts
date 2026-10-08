import type { Queue, QueueCase } from './types';

const STRENGTH_MULT: Record<string, number> = { strong: 1, moderate: 0.75, weak: 0.4 };

/**
 * Fixture-mode stand-in for Part A's optimizer (A13), so the capacity slider re-plans live
 * before the engine exists. Same formula as the spec; greedy by value per hour instead of CP-SAT.
 */
export function replanLocal(q: Queue, capacity: number, horizon: number): Queue {
  const eligible = (c: QueueCase) => c.status !== 'cleared' && c.status !== 'monitor';
  const value = (c: QueueCase) => {
    const future = (c.horizon_risk[String(horizon)] ?? 0) * c.expected_recovery * 0.25 * (horizon / 30);
    return (c.expected_recovery + future) * (1 + c.member_harm) * (0.8 + 0.1 * c.severity) * (STRENGTH_MULT[c.evidence_strength] ?? 0.5);
  };
  const scored = q.cases.map(c => ({ ...c, priority_score: Math.round(value(c) / Math.max(c.effort_hours, 1)) }));
  const explorationBudget = Math.round(capacity * 0.1);
  const mainBudget = capacity - explorationBudget;

  const byValue = [...scored].filter(c => eligible(c) && !c.exploration).sort((a, b) => b.priority_score - a.priority_score);
  let used = 0;
  const picked = new Set<string>();
  for (const c of byValue) if (used + c.effort_hours <= mainBudget) { picked.add(c.case_id); used += c.effort_hours; }
  let expUsed = 0;
  for (const c of scored.filter(c => eligible(c) && c.exploration)) if (expUsed + c.effort_hours <= explorationBudget) { picked.add(c.case_id); expUsed += c.effort_hours; }

  const ranked = [...scored].sort((a, b) => b.priority_score - a.priority_score).map((c, i) => {
    const selected = picked.has(c.case_id);
    const perHour = Math.round(c.expected_recovery / Math.max(c.effort_hours, 1));
    let reason = c.selection_reason;
    if (selected && c.exploration) reason = 'Exploration: anomaly-only pattern unlike past confirmed fraud';
    else if (selected) reason = `Selected: ₹${perHour.toLocaleString('en-IN')} expected recovery per hour`;
    else if (!eligible(c)) reason = `Not eligible: status ${c.status.replace(/_/g, ' ')}`;
    else if (c.evidence_strength === 'weak') reason = `Not selected: weak evidence, ${c.effort_hours} h effort, ₹${perHour.toLocaleString('en-IN')} per hour`;
    else reason = `Not selected: doesn't fit remaining ${Math.max(mainBudget - used, 0)} h of capacity`;
    return { ...c, rank: i + 1, selected, recovery_per_hour: perHour, selection_reason: reason };
  });

  const sel = ranked.filter(c => c.selected);
  const recovery = sel.reduce((s, c) => s + c.expected_recovery, 0);
  const hours = sel.reduce((s, c) => s + c.effort_hours, 0);
  let cum = 0, h = 0;
  const frontier = [{ hours: 0, cumulative_recovery: 0 }, ...[...scored].filter(eligible)
    .sort((a, b) => b.expected_recovery / b.effort_hours - a.expected_recovery / a.effort_hours)
    .map(c => { h += c.effort_hours; cum += c.expected_recovery; return { hours: h, cumulative_recovery: cum }; })];

  return {
    ...q, capacity_hours: capacity, horizon, cases: ranked, selected_count: sel.length, hours_used: hours,
    exploration_hours_reserved: explorationBudget, expected_recovery_selected: recovery,
    recovery_per_hour: hours ? Math.round(recovery / hours) : 0, frontier,
  };
}

export const inr = (v: number | null | undefined, compact = true): string => {
  if (v == null || Number.isNaN(v)) return '—';
  if (compact && Math.abs(v) >= 1e7) return `₹${(v / 1e7).toFixed(2)}Cr`;
  if (compact && Math.abs(v) >= 1e5) return `₹${(v / 1e5).toFixed(2)}L`;
  return `₹${Math.round(v).toLocaleString('en-IN')}`;
};

export const num = (v: number | null | undefined, digits = 0): string =>
  v == null ? '—' : v.toLocaleString('en-IN', { maximumFractionDigits: digits, minimumFractionDigits: 0 });

export const pct = (v: number | null | undefined, digits = 0): string =>
  v == null ? '—' : `${(v * 100).toFixed(digits)}%`;

export const titleCase = (s: string): string => s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

export const STATUS: Record<string, { label: string; tone: 'bad' | 'warn' | 'accent' | 'good' | 'neutral' }> = {
  needs_siu_review: { label: 'Needs SIU review', tone: 'bad' },
  request_documentation: { label: 'Request documentation', tone: 'warn' },
  monitor: { label: 'Monitor', tone: 'accent' },
  cleared: { label: 'Cleared', tone: 'good' },
  confirmed_by_human: { label: 'Confirmed by investigator', tone: 'bad' },
};

export const PATTERN: Record<string, string> = {
  claim_splitting_network: 'Claim-splitting network',
  referral_ring: 'Referral ring',
  phantom_services: 'Phantom services',
  upcoding_drift: 'Upcoding drift',
  duplicate_billing: 'Duplicate billing',
  identity_cluster: 'Identity cluster',
  unbundling: 'Unbundling',
  impossible_timing: 'Impossible timing',
  mixed: 'Mixed signals',
};

export const METHOD_LABEL: Record<string, string> = { rules: 'Rules', anomaly: 'Peer anomaly', temporal: 'Temporal', graph: 'Graph' };

/** Format an evidence value by its unit, matching how the agents and verifier read it. */
export const fmtUnit = (v: number | null | undefined, unit = ''): string => {
  if (v == null) return '—';
  switch (unit) {
    case 'share': return pct(v);
    case 'inr': return inr(v);
    case 'percentile': return v <= 1 ? `${(v * 100).toFixed(0)}th pct` : `${v.toFixed(0)}th pct`;
    case 'days': return `${num(v)} d`;
    default: return num(v, 2);
  }
};

export const relDays = (d: number | null | undefined): string =>
  d == null ? 'No pending release' : d <= 0 ? 'Releases today' : d === 1 ? 'Releases tomorrow' : `Releases in ${d} days`;

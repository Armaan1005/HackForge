// Small animated diagrams of the six Fraud Twin schemes. Green = normal, amber = the fraud pattern.
const G = 'var(--series-1)', A = 'var(--series-2)', M = 'var(--mark-muted)', T = 'var(--text-3)';

function Splitting() {
  return (
    <svg viewBox="0 0 160 90" className="sa">
      <line x1="8" y1="38" x2="152" y2="38" stroke={T} strokeDasharray="3 3" />
      <text x="152" y="33" textAnchor="end" fontSize="8" fill={T}>₹50,000 limit</text>
      <rect x="14" y="12" width="22" height="66" rx="3" fill={M} />
      <text x="25" y="88" textAnchor="middle" fontSize="7" fill={T}>₹2L</text>
      <path d="M42 45 L56 45" stroke={T} strokeWidth="1.2" markerEnd="url(#sa-arr)" />
      {[0, 1, 2, 3].map(i => <rect key={i} className="sa-pop" style={{ animationDelay: `${i * 0.15}s` }} x={66 + i * 22} y="42" width="16" height="36" rx="3" fill={A} />)}
      <defs><marker id="sa-arr" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill={T} /></marker></defs>
    </svg>
  );
}

function Referral() {
  const pts = [[80, 14], [126, 46], [80, 78], [34, 46]];
  return (
    <svg viewBox="0 0 160 90" className="sa">
      <path d="M80 14 Q118 14 126 46 Q118 78 80 78 Q42 78 34 46 Q42 14 80 14" fill="none" stroke={A} strokeWidth="1.6" strokeDasharray="5 4" className="sa-flow" />
      {pts.map(([x, y], i) => <circle key={i} cx={x} cy={y} r="8" fill={i % 2 ? A : G} stroke="var(--surface)" strokeWidth="2" />)}
      <circle cx="80" cy="46" r="6" fill="none" stroke={T} strokeDasharray="2 2" />
      <text x="80" y="49" textAnchor="middle" fontSize="7" fill={T}>₹</text>
    </svg>
  );
}

function Phantom() {
  return (
    <svg viewBox="0 0 160 90" className="sa">
      <rect x="54" y="20" width="62" height="50" rx="6" fill={A} opacity=".12" />
      <text x="85" y="15" textAnchor="middle" fontSize="8" fill={T}>admitted elsewhere</text>
      <line x1="8" y1="70" x2="152" y2="70" stroke={T} />
      {[20, 38, 64, 80, 98, 128, 144].map((x, i) => {
        const inside = x > 54 && x < 116;
        return <circle key={x} className={inside ? 'sa-ghost' : ''} style={{ animationDelay: `${i * 0.2}s` }} cx={x} cy="56" r="5" fill={inside ? A : G} />;
      })}
      <text x="85" y="84" textAnchor="middle" fontSize="7" fill={T}>home visits billed</text>
    </svg>
  );
}

function Upcoding() {
  return (
    <svg viewBox="0 0 160 90" className="sa">
      <line x1="12" y1="76" x2="150" y2="76" stroke={T} />
      <path d="M14 70 C50 68, 80 56, 110 36 S140 16, 148 14" fill="none" stroke={A} strokeWidth="2.2" className="sa-draw" />
      <path d="M14 70 C50 69, 100 68, 148 66" fill="none" stroke={G} strokeWidth="1.6" strokeDasharray="3 3" />
      <text x="148" y="62" textAnchor="end" fontSize="7" fill={T}>peers</text>
      <text x="148" y="11" textAnchor="end" fontSize="7" fill={T}>level-5 share</text>
      <text x="14" y="86" fontSize="7" fill={T}>month 1</text><text x="148" y="86" textAnchor="end" fontSize="7" fill={T}>month 12</text>
    </svg>
  );
}

function Identity() {
  const ring = Array.from({ length: 8 }, (_, i) => [80 + 52 * Math.cos((i / 8) * Math.PI * 2), 45 + 30 * Math.sin((i / 8) * Math.PI * 2)]);
  return (
    <svg viewBox="0 0 160 90" className="sa">
      {ring.map(([x, y], i) => <line key={i} x1="80" y1="45" x2={x} y2={y} stroke={A} strokeOpacity=".5" />)}
      {ring.map(([x, y], i) => <circle key={i} className="sa-pop" style={{ animationDelay: `${i * 0.08}s` }} cx={x} cy={y} r="5" fill={M} stroke="var(--surface)" strokeWidth="1.5" />)}
      <rect x="71" y="36" width="18" height="18" rx="5" fill={A} />
      <text x="80" y="49" textAnchor="middle" fontSize="10" fill="#fff">☎</text>
    </svg>
  );
}

function Duplicate() {
  const Receipt = ({ x, y, c }: { x: number; y: number; c: string }) => (
    <g transform={`translate(${x} ${y})`}>
      <rect width="40" height="52" rx="4" fill="var(--surface)" stroke={c} strokeWidth="1.5" />
      {[12, 20, 28].map(l => <line key={l} x1="7" y1={l} x2="33" y2={l} stroke={M} strokeWidth="2" />)}
      <text x="20" y="44" textAnchor="middle" fontSize="8" fontWeight="700" fill={c}>₹4,800</text>
    </g>
  );
  return (
    <svg viewBox="0 0 160 90" className="sa">
      <Receipt x={34} y={16} c={G} />
      <g className="sa-slide"><Receipt x={84} y={24} c={A} /></g>
      <text x="104" y="86" textAnchor="middle" fontSize="7" fill={T}>same claim, 3 days later</text>
    </svg>
  );
}

export const SCHEME_ART: Record<string, { art: () => JSX.Element; line: string }> = {
  claim_splitting: { art: Splitting, line: 'One big bill cut into claims that each stay under the review limit.' },
  referral_collusion: { art: Referral, line: 'Providers passing patients round a ring, often behind one owner or bank account.' },
  phantom_services: { art: Phantom, line: 'Care billed that never happened: after death, during an admission, or inflated miles.' },
  upcoding_drift: { art: Upcoding, line: 'Visits slowly shifted to the top billing level while peers stay flat.' },
  identity_cluster: { art: Identity, line: 'Many fake or borrowed member identities sharing one phone or address.' },
  duplicate_billing: { art: Duplicate, line: 'The same service billed again, sometimes days later with a tweaked price.' },
};

import { Bot, Gavel, Network, Scale, ShieldAlert, SlidersHorizontal, UserCheck } from 'lucide-react';
import { Sheet } from './ui';

const steps = [
  { icon: SlidersHorizontal, title: 'You enter', body: "Today's investigator capacity (hours) and a risk horizon (30/60/90 days). Optionally a \"what if\" attack for the Fraud Twin." },
  { icon: Network, title: 'Code detects', body: 'Four complementary methods on synthetic claims: rules, peer anomaly scoring, temporal analytics and graph analytics across providers, members, facilities, referrals, owners and locations.' },
  { icon: Scale, title: 'Code tries to explain alerts away first', body: 'Exoneration rules (sole rural provider, case-mix adjustment, corrected claims, seasonal events…) clear most alerts before a human sees them. Hard signals are never cleared.' },
  { icon: ShieldAlert, title: 'Code scores and ranks', body: 'Risk, rupees at risk, member harm, severity, evidence strength and effort feed a portfolio optimizer that fills your capacity with the most valuable cases, plus a 10% exploration reserve.' },
  { icon: Gavel, title: 'Gemini argues, never decides', body: 'Prosecution and Defense argue from the same evidence; a Verdict Clerk words the code-computed status; Document Forensics checks records for fabricated or injected content.' },
  { icon: Bot, title: 'Citation Verifier', body: 'Plain code drops any AI statement that cites missing evidence or states a number the engine never produced. Removed statements are counted on screen.' },
  { icon: UserCheck, title: 'A human decides', body: 'Confirm, clear, request more information or hold payment. Every action is logged. No automatic denial, no fraud finding.' },
];

export function HowItWorks({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Sheet open={open} onClose={onClose} title="How Axon works">
      <p className="muted" style={{ marginBottom: 16 }}>Axon turns thousands of unexplained alerts into a short, ranked list of evidence-backed cases an investigator can act on.</p>
      <div className="stack">
        {steps.map((s, i) => (
          <div key={s.title} className="row-nw" style={{ alignItems: 'flex-start', gap: 14 }}>
            <span style={{ width: 34, height: 34, borderRadius: 10, background: 'var(--accent-soft)', color: 'var(--accent)', display: 'grid', placeItems: 'center', flex: 'none' }}><s.icon size={17} /></span>
            <div><div className="strong">{i + 1}. {s.title}</div><div className="small muted">{s.body}</div></div>
          </div>
        ))}
      </div>
      <div className="divider" />
      <div className="stack-sm small muted">
        <b style={{ color: 'var(--text)' }}>When Axon is uncertain</b>
        <span>• Weak or missing evidence → status becomes <b>Request documentation</b>, not escalation.</span>
        <span>• Small peer groups, short provider history and missing records are listed as limitations on every case.</span>
        <span>• If Gemini is slow or unavailable, deterministic summaries appear, labelled as templates.</span>
        <span>• If a detection layer fails, the case shows it as unavailable instead of guessing.</span>
        <span>• All data is synthetic. No real patients, members or providers.</span>
      </div>
    </Sheet>
  );
}

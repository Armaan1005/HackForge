import { Gavel, Network, Scale, SlidersHorizontal, UserCheck } from 'lucide-react';
import { Sheet } from './ui';

const steps = [
  { icon: SlidersHorizontal, title: 'You set capacity', body: 'Investigator hours and a 30/60/90-day horizon.' },
  { icon: Network, title: 'Code detects', body: 'Rules, peer anomaly, temporal and graph analytics.' },
  { icon: Scale, title: 'Code explains alerts away', body: 'Most alerts are cleared with a reason before you see them.' },
  { icon: Gavel, title: 'AI argues both sides', body: 'Every statement is checked against the evidence.' },
  { icon: UserCheck, title: 'You decide', body: 'Nothing is denied or held automatically.' },
];

export function HowItWorks({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Sheet open={open} onClose={onClose} title="How Axon works">
      <div className="stack">
        {steps.map((s, i) => (
          <div key={s.title} className="row-nw" style={{ gap: 14 }}>
            <span className="step-icon"><s.icon size={16} /></span>
            <div><div className="strong">{i + 1}. {s.title}</div><div className="small muted">{s.body}</div></div>
          </div>
        ))}
      </div>
      <div className="divider" />
      <p className="small muted">When unsure, Axon asks for documents instead of escalating. All data is synthetic.</p>
    </Sheet>
  );
}

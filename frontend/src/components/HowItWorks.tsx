import { Mascot } from './Mascot';
import { Sheet } from './ui';

const steps = [
  { title: 'You set the hours', body: 'How much investigator time you have, and how far ahead to look.', ai: false },
  { title: 'Code finds patterns', body: 'Rules, peer comparison, timing and the network between providers.', ai: false },
  { title: 'Code explains alerts away', body: 'Rural hospitals, sicker patients, corrected claims: cleared with a reason.', ai: false },
  { title: 'AI argues both sides', body: 'Every sentence must point to evidence, or it is removed.', ai: true },
  { title: 'You decide', body: 'Nothing is denied or held without you.', ai: false },
];

export function HowItWorks({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Sheet open={open} onClose={onClose} title="How Axon works" wide>
      <div className="row-flex" style={{ alignItems: 'flex-end', gap: 18, marginBottom: 22 }}>
        <Mascot size={84} mood="watching" />
        <p className="muted" style={{ maxWidth: '52ch' }}>Argus keeps watch over thousands of claims so your team only spends time on the few that matter, with the evidence ready.</p>
      </div>
      <div className="track-steps">
        <ol>
          {steps.map((s, i) => (
            <li key={s.title}>
              <span className={`track-dot ${s.ai ? 'ai' : ''}`}>{i + 1}</span>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </li>
          ))}
        </ol>
      </div>
      <div className="divider" style={{ margin: '24px 0 16px' }} />
      <p className="small muted">When Axon isn't sure, it asks for documents instead of escalating. All data here is synthetic.</p>
    </Sheet>
  );
}

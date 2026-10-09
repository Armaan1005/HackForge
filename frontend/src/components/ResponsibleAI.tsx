// "Responsible AI" on the Trust page: the three commitments (explain limits, human in the loop, fail safely),
// each backed by concrete, mostly live, proof and a link to where it happens in the product.
import { Link } from 'react-router-dom';
import { num } from '../lib/format';
import { Icon, type IconName } from './Icon';

interface Props {
  struck: number | null;          // AI statements the Citation Verifier blocked
  checked: number | null;         // AI statements checked
  decisions: number;              // entries in the audit trail
  wronglyCleared: number;         // planted fraud the engine cleared by mistake
}

export function ResponsibleAI({ struck, checked, decisions, wronglyCleared }: Props) {
  const pillars: { icon: IconName; title: string; promise: string; proof: string[]; to: string; see: string }[] = [
    {
      icon: 'hint', title: 'Explains its limits', promise: 'Axon says what it can’t be sure about, next to every finding.',
      proof: [
        'Every case lists “What Axon can’t be sure about”: short provider history, missing records, layers that didn’t run.',
        'Confidence is labelled a heuristic from method agreement, not a probability.',
        'Possible innocent explanations sit beside the evidence, and the defense argues them in court.',
        'Law pages are marked as paraphrases to check against the official text.',
      ],
      to: '/cases/CASE-0002', see: 'See a case',
    },
    {
      icon: 'employee', title: 'Keeps a person in charge', promise: 'Axon recommends. A named investigator decides.',
      proof: [
        'No claim is denied and no payment is held unless an investigator chooses to; Axon never acts on its own.',
        'Scores, statuses and ₹ figures come from code; the AI only words them and argues both sides.',
        `Every decision is recorded in the audit trail${decisions ? ` (${num(decisions)} entries so far)` : ''}.`,
        'Fraud Twin fixes are tested on a sandbox copy and only apply after someone approves them.',
      ],
      to: '/court', see: 'See the Evidence Court',
    },
    {
      icon: 'shield', title: 'Fails safely', promise: 'When something breaks, Axon falls back to the evidence, never to a guess.',
      proof: [
        struck != null
          ? `${num(struck)} AI statement${struck === 1 ? '' : 's'} struck so far${checked ? ` out of ${num(checked)} checked` : ''}: no evidence, or a number the engine never produced.`
          : 'Any AI statement without evidence, or with a number the engine never produced, is struck.',
        'If the AI is down or slow, every agent falls back to wording built from the engine’s evidence.',
        'Instructions hidden in medical records are treated as text, ignored and flagged.',
        `Hard signals are never auto-cleared; ${wronglyCleared} planted fraud case${wronglyCleared === 1 ? '' : 's'} cleared by mistake.`,
      ],
      to: '/cases/CASE-0002?tab=documents', see: 'See records checks',
    },
  ];

  return (
    <section className="rai" aria-label="Responsible AI">
      <div className="rai-head">
        <p className="eyebrow">Responsible AI</p>
        <h2>Built to be checked, not trusted blindly</h2>
      </div>
      <div className="rai-grid">
        {pillars.map(p => (
          <div key={p.title} className="rai-col">
            <span className="row-icon"><Icon name={p.icon} size={16} /></span>
            <b>{p.title}</b>
            <p className="rai-promise">{p.promise}</p>
            <ul>{p.proof.map(x => <li key={x}>{x}</li>)}</ul>
            <Link to={p.to} className="scheme-try">{p.see} <Icon name="arrow-right" size={13} /></Link>
          </div>
        ))}
      </div>
    </section>
  );
}

import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { Rule } from '../lib/types';
import { Icon } from './Icon';
import { Note, Section, Sheet } from './ui';

const isRule = (id: string) => /^(POL|LAW)-/.test(id);
export const splitIds = (ids: string[]) => ({ evidence: ids.filter(i => !isRule(i)), rules: ids.filter(isRule) });

function RuleSheet({ r, onClose }: { r: Rule | null; onClose: () => void }) {
  return (
    <Sheet open={!!r} onClose={onClose} title={r ? `${r.id} · ${r.title}` : ''}>
      {r && <div className="stack">
        <p>{r.text}</p>
        <p className="small muted">Source: {r.source}</p>
        {r.kind === 'law'
          ? <Note tone="warn" icon="official-service">A short paraphrase of a public law, possibly relevant here. Not legal advice and not a finding: check the official text before relying on it.</Note>
          : <Note icon="course-book">Example payer rule, written for this prototype.</Note>}
        <p className="xs faint">Found by keyword search over the rulebook for this case. Rules give context only; they never change the risk score.</p>
        <Link to={`/rulebook?rule=${r.id}`} className="btn btn-secondary btn-sm" style={{ justifySelf: 'start' }}><Icon name="course-book" size={14} />Open in the rulebook</Link>
      </div>}
    </Sheet>
  );
}

/** Small chip for a POL-/LAW- citation; opens the rule text. */
export function RuleChip({ id, rules }: { id: string; rules: Rule[] }) {
  const [open, setOpen] = useState(false);
  const r = rules.find(x => x.id === id) ?? null;
  return (
    <>
      <button type="button" className={`cite rule ${id.startsWith('LAW') ? 'law' : ''}`} title={r?.title ?? id} onClick={() => setOpen(true)}>
        <Icon name={id.startsWith('LAW') ? 'official-service' : 'course-book'} size={10} className="inline" />{id}
      </button>
      <RuleSheet r={open ? r : null} onClose={() => setOpen(false)} />
    </>
  );
}

/** "Rules on the bench": everything retrieved for this case, cited ones first. */
export function RulesPanel({ rules }: { rules: Rule[] }) {
  const [open, setOpen] = useState<Rule | null>(null);
  if (!rules.length) return null;
  return (
    <>
      <Section title="Policies and laws that may apply">
        {rules.map(r => (
          <div key={r.id} className="row clickable" role="button" tabIndex={0} onClick={() => setOpen(r)} onKeyDown={e => e.key === 'Enter' && setOpen(r)}>
            <span className={`row-icon ${r.kind === 'law' ? 'warn' : ''}`}><Icon name={r.kind === 'law' ? 'official-service' : 'course-book'} size={15} /></span>
            <div className="row-text">
              <span className="row-label">{r.title} <span className="faint small">· {r.id}</span></span>
              <span className="row-desc clamp-1">{r.kind === 'law' ? 'Law summary · verify before use' : 'Payer rule'}</span>
            </div>
            {r.cited && <span className="review-pill review-done">Cited</span>}
            <Icon name="slim-arrow-right" size={14} className="muted" />
          </div>
        ))}
      </Section>
      <RuleSheet r={open} onClose={() => setOpen(null)} />
    </>
  );
}

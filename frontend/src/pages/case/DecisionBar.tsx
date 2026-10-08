import { AlarmClock, CheckCircle2, CircleHelp, ShieldCheck, ShieldX } from 'lucide-react';
import { useState } from 'react';
import { Banner, Button, Sheet } from '../../components/ui';
import { api } from '../../lib/api';
import { inr } from '../../lib/format';
import type { CaseDetail } from '../../lib/types';

const ACTIONS = {
  confirm: { label: 'Investigate', icon: ShieldX, variant: 'bad' as const, desc: 'Assign an investigator. Starts a human review, not a fraud finding.' },
  need_more_info: { label: 'Request records', icon: CircleHelp, variant: 'warn' as const, desc: 'Ask the provider for missing documents first.' },
  clear: { label: 'Clear', icon: ShieldCheck, variant: 'good' as const, desc: 'Close with no action.' },
  hold_payment: { label: 'Hold payment', icon: AlarmClock, variant: 'secondary' as const, desc: 'Hold pending claims until records arrive. Reversible.' },
};
type Action = keyof typeof ACTIONS;

export function DecisionBar({ k }: { k: CaseDetail }) {
  const [open, setOpen] = useState<Action | null>(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ action: Action; id: string } | null>(null);

  const submit = async () => {
    if (!open) return;
    setBusy(true);
    try {
      const res = (await api.decision(k.case_id, open, note)) as { decision_id: string };
      setDone({ action: open, id: res.decision_id });
      setOpen(null); setNote('');
    } finally { setBusy(false); }
  };

  return (
    <div className="no-print stack-sm">
      <div className="row">
        {(Object.keys(ACTIONS) as Action[]).filter(a => a !== 'hold_payment' || k.money.pending > 0).map(a => {
          const A = ACTIONS[a];
          return <Button key={a} size="sm" variant={A.variant} icon={A.icon} onClick={() => setOpen(a)}>{A.label}</Button>;
        })}
        <span className="xs faint">You decide. Every action is logged.</span>
      </div>
      {done && <Banner tone="good" icon={CheckCircle2}>{ACTIONS[done.action].label} logged as {done.id}.</Banner>}
      <Sheet open={!!open} onClose={() => setOpen(null)} title={open ? ACTIONS[open].label : ''}
        footer={<><Button variant="ghost" onClick={() => setOpen(null)}>Cancel</Button><Button variant={open ? ACTIONS[open].variant : 'primary'} loading={busy} onClick={submit}>Confirm</Button></>}>
        {open && (
          <div className="stack">
            <p className="muted">{ACTIONS[open].desc}</p>
            {open === 'hold_payment' && <Banner tone="warn">{k.payment_clock.pending_claims} claims · {inr(k.payment_clock.pending_amount)}</Banner>}
            {open === 'confirm' && k.missing_documents.some(m => m.critical) && <Banner tone="warn">Critical documents are still missing.</Banner>}
            <textarea className="textarea" value={note} onChange={e => setNote(e.target.value)} placeholder="Note (optional)" aria-label="Note for the audit log" />
          </div>
        )}
      </Sheet>
    </div>
  );
}

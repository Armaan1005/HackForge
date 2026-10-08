import { AlarmClock, CheckCircle2, CircleHelp, ShieldCheck, ShieldX } from 'lucide-react';
import { useState } from 'react';
import { Banner, Button, Card, Sheet } from '../../components/ui';
import { api } from '../../lib/api';
import { inr } from '../../lib/format';
import type { CaseDetail } from '../../lib/types';

const ACTIONS = {
  confirm: { label: 'Open investigation', icon: ShieldX, variant: 'bad' as const, desc: 'Assign an investigator. This is not a fraud finding; it starts a human review.' },
  need_more_info: { label: 'Request records', icon: CircleHelp, variant: 'warn' as const, desc: 'Ask the provider for the missing documents before deciding.' },
  clear: { label: 'Clear provider', icon: ShieldCheck, variant: 'good' as const, desc: 'Close with no action. Feeds back so similar legitimate patterns rank lower.' },
  hold_payment: { label: 'Hold payment', icon: AlarmClock, variant: 'secondary' as const, desc: 'Hold pending claims until records arrive. Logged and reversible.' },
};
type Action = keyof typeof ACTIONS;

export function DecisionBar({ k }: { k: CaseDetail }) {
  const [open, setOpen] = useState<Action | null>(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ action: Action; res: Record<string, unknown> } | null>(null);

  const submit = async () => {
    if (!open) return;
    setBusy(true);
    try {
      const res = await api.decision(k.case_id, open, note);
      setDone({ action: open, res: res as Record<string, unknown> });
      setOpen(null); setNote('');
    } finally { setBusy(false); }
  };

  return (
    <Card tight className="no-print">
      <div className="row between">
        <div className="small"><b>Your decision.</b> <span className="muted">Axon recommends; it never acts on its own. Every action is logged to the audit trail.</span></div>
        <div className="row">
          {(Object.keys(ACTIONS) as Action[]).filter(a => a !== 'hold_payment' || k.money.pending > 0).map(a => {
            const A = ACTIONS[a];
            return <Button key={a} size="sm" variant={A.variant} icon={A.icon} onClick={() => setOpen(a)}>{A.label}{a === 'hold_payment' && k.payment_clock.hold_recommended ? ' (recommended)' : ''}</Button>;
          })}
        </div>
      </div>
      {done && (
        <div style={{ marginTop: 12 }}>
          <Banner tone="good" icon={CheckCircle2}>
            <b>{ACTIONS[done.action].label}</b> recorded as {String(done.res.decision_id)} at {String(done.res.recorded_at)}.
            {Array.isArray(done.res.weight_changes) && done.res.weight_changes.length > 0 && <> Detection weights adjusted: {(done.res.weight_changes as { method: string; before: number; after: number }[]).map(w => `${w.method} ${w.before}→${w.after}`).join(', ')}.</>}
            {done.res.local ? ' (Saved locally: engine not running.)' : ''}
          </Banner>
        </div>
      )}
      <Sheet open={!!open} onClose={() => setOpen(null)} title={open ? ACTIONS[open].label : ''}
        footer={<><Button variant="ghost" onClick={() => setOpen(null)}>Cancel</Button><Button variant={open ? ACTIONS[open].variant : 'primary'} loading={busy} onClick={submit}>Confirm and log</Button></>}>
        {open && (
          <div className="stack">
            <p className="muted">{ACTIONS[open].desc}</p>
            {open === 'hold_payment' && <Banner tone="warn">Holds {k.payment_clock.pending_claims} pending claims worth {inr(k.payment_clock.pending_amount)} due {k.payment_clock.next_release_date ?? 'soon'}.</Banner>}
            {open === 'confirm' && k.missing_documents.some(m => m.critical) && <Banner tone="warn">Critical documents are still missing. Consider "Request records" first.</Banner>}
            <label className="stack-sm"><span className="small strong">Note for the audit log</span>
              <textarea className="textarea" value={note} onChange={e => setNote(e.target.value)} placeholder="Why you're making this decision (optional)" /></label>
            <span className="xs faint">Case {k.case_id} · status computed by the engine: {k.verdict.status.replace(/_/g, ' ')}</span>
          </div>
        )}
      </Sheet>
    </Card>
  );
}

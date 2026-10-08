import { useState } from 'react';
import { Icon } from '../../components/Icon';
import { toast } from '../../components/Toasts';
import { INVESTIGATOR } from '../../components/TopNav';
import { Button } from '../../components/ui';
import { api } from '../../lib/api';
import type { CaseDetail } from '../../lib/types';

const SUGGESTS: Record<string, string> = { needs_siu_review: 'a full SIU review', request_documentation: 'asking for records first', monitor: 'keeping an eye on it', cleared: 'clearing it' };
const LABEL: Record<string, string> = { confirm: 'Investigation opened', need_more_info: 'Records requested', clear: 'Provider cleared', hold_payment: 'Payment held' };

/** Human in the loop: the engine's status is a draft until a person acts. */
export function DecisionBox({ k }: { k: CaseDetail }) {
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [done, setDone] = useState<{ action: string; id: string; at: string } | null>(null);

  const decide = async (action: string) => {
    setBusy(action);
    try {
      const r = (await api.decision(k.case_id, action, note, INVESTIGATOR.name)) as { decision_id: string; recorded_at: string };
      setDone({ action, id: r.decision_id, at: r.recorded_at });
      setNote('');
      toast({ title: LABEL[action], body: 'Saved in the audit trail.', icon: action === 'clear' ? 'accept' : action === 'hold_payment' ? 'pending' : 'flag' });
    } catch (e) {
      toast({ title: 'Not saved', body: (e as Error).message, icon: 'alert' });
    } finally { setBusy(null); }
  };

  if (done) return (
    <div className="review-box done">
      <div className="row-nw"><Icon name="accept" size={16} /><b>{LABEL[done.action]} by {INVESTIGATOR.name.split(' ')[0]}</b></div>
      <p className="small muted" style={{ marginTop: 6 }}>{done.id} · {done.at.replace('T', ' ')}</p>
      <Button variant="ghost" size="sm" style={{ marginTop: 8 }} onClick={() => setDone(null)}>Change decision</Button>
    </div>
  );

  return (
    <div className="review-box">
      <div className="row-nw" style={{ marginBottom: 6 }}><Icon name="shield" size={16} /><h2 style={{ fontSize: '1.1rem' }}>Human review needed</h2></div>
      <p className="small" style={{ marginBottom: 10 }}>Axon suggests <b>{SUGGESTS[k.verdict.status] ?? k.verdict.status.replace(/_/g, ' ')}</b>. Nothing happens until you decide.</p>
      <ul className="list-check" style={{ marginBottom: 12 }}>
        {k.verdict.reasons.map(r => <li key={r}><Icon name="message-information" size={14} /><span className="small">{r}</span></li>)}
      </ul>
      <textarea className="textarea" style={{ minHeight: 64, marginBottom: 10 }} placeholder="Note for the audit trail (optional)" value={note} onChange={e => setNote(e.target.value)} />
      <div className="row-flex">
        <Button size="sm" icon="flag" loading={busy === 'confirm'} onClick={() => decide('confirm')}>Open investigation</Button>
        <Button size="sm" variant="tinted" icon="documents" loading={busy === 'need_more_info'} onClick={() => decide('need_more_info')}>Request records</Button>
        {k.money.pending > 0 && <Button size="sm" variant="secondary" icon="pending" loading={busy === 'hold_payment'} onClick={() => decide('hold_payment')}>Hold payment</Button>}
        <Button size="sm" variant="danger" loading={busy === 'clear'} onClick={() => decide('clear')}>Clear</Button>
      </div>
    </div>
  );
}

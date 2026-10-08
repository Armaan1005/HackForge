import type { Rule } from '../../lib/types';
import { useState } from 'react';
import { Icon } from '../../components/Icon';
import { Mascot } from '../../components/Mascot';
import { RuleChip } from '../../components/Rules';
import { Button, Card, Chip, Cite } from '../../components/ui';
import { ai } from '../../lib/api';
import type { CaseDetail } from '../../lib/types';

const SUGGESTIONS = ['Why is this case ranked so high?', 'What would clear this provider?', 'Which records should I ask for first?'];

export function AskTab({ k }: { k: CaseDetail }) {
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [thread, setThread] = useState<{ q: string; a: string; ids: string[]; grounded: boolean; rules?: Rule[] }[]>([]);
  const ask = async (question: string) => {
    if (!question.trim()) return;
    setBusy(true);
    try {
      const r = await ai.ask(k.case_id, question);
      setThread(t => [...t, { q: question, a: r.answer, ids: r.evidence_ids, grounded: r.grounded, rules: r.rules ?? [] }]);
      setQ('');
    } catch (e) {
      setThread(t => [...t, { q: question, a: `I couldn't reach the AI service (${(e as Error).message}).`, ids: [], grounded: false }]);
    } finally { setBusy(false); }
  };
  return (
    <Card style={{ maxWidth: 820 }}>
      <div className="row-flex" style={{ alignItems: 'flex-end', marginBottom: 16 }}>
        <Mascot size={64} mood={busy ? 'thinking' : 'watching'} />
        <div className="bubble">Ask me about this case. I only answer from its evidence.</div>
      </div>
      <div className="stack">
        {thread.map((t, i) => (
          <div key={i} className="stack-sm">
            <b>{t.q}</b>
            <div className="help-panel">
              <p>{t.a}{t.ids.map(id => /^(POL|LAW)-/.test(id) ? <RuleChip key={id} id={id} rules={t.rules ?? []} /> : <Cite key={id} id={id} />)}</p>
              {!t.grounded && <p className="xs faint" style={{ marginTop: 6 }}>Not fully backed by evidence. Check the evidence list.</p>}
            </div>
          </div>
        ))}
        <div className="chip-group">{SUGGESTIONS.map(s => <Chip key={s} onClick={() => ask(s)}>{s}</Chip>)}</div>
        <form className="row-nw" onSubmit={e => { e.preventDefault(); ask(q); }}>
          <input className="input" value={q} onChange={e => setQ(e.target.value)} placeholder="Ask a question…" maxLength={500} />
          <Button type="submit" loading={busy} icon="feeder-arrow">Ask</Button>
        </form>
      </div>
      <p className="xs faint" style={{ marginTop: 10 }}><Icon name="complete" size={12} className="inline" /> Every answer is checked against the case evidence.</p>
    </Card>
  );
}

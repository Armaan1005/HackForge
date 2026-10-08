import { Bot, Send } from 'lucide-react';
import { useState } from 'react';
import { Button, Card, Cite, SourceBadge } from '../../components/ui';
import { ai } from '../../lib/api';
import type { CaseDetail } from '../../lib/types';

const SUGGESTIONS = [
  'Why is this ranked above other cases?',
  'What would clear this provider?',
  'Which documents should I request first?',
];

export function AskTab({ k }: { k: CaseDetail }) {
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [thread, setThread] = useState<{ q: string; a: string; ids: string[]; grounded: boolean; source: string }[]>([]);
  const ask = async (question: string) => {
    if (!question.trim()) return;
    setBusy(true);
    try {
      const r = await ai.ask(k.case_id, question);
      setThread(t => [...t, { q: question, a: r.answer, ids: r.evidence_ids, grounded: r.grounded, source: r.source }]);
      setQ('');
    } catch (e) {
      setThread(t => [...t, { q: question, a: `Assistant unavailable: ${(e as Error).message}`, ids: [], grounded: false, source: 'error' }]);
    } finally { setBusy(false); }
  };
  return (
    <Card title="Ask the case" icon={Bot} action={<span className="xs faint">answers cite this case only</span>}>
      <div className="stack">
        {thread.map((t, i) => (
          <div key={i} className="stack-sm">
            <div className="small strong">{t.q}</div>
            <div className="small" style={{ background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 12, padding: '10px 12px' }}>
              {t.a}{t.ids.map(id => <Cite key={id} id={id} />)}
              <div className="row xs faint" style={{ marginTop: 6 }}><SourceBadge source={t.source === 'llm' ? 'llm' : undefined} />{t.grounded ? 'Grounded in cited evidence' : 'Not fully grounded: check the evidence list'}</div>
            </div>
          </div>
        ))}
        <div className="row">{SUGGESTIONS.map(s => <button key={s} className="chip chip-outline" style={{ cursor: 'pointer', border: 0 }} onClick={() => ask(s)}>{s}</button>)}</div>
        <form className="row-nw" onSubmit={e => { e.preventDefault(); ask(q); }}>
          <input className="input" value={q} onChange={e => setQ(e.target.value)} placeholder="Ask about this case…" maxLength={500} />
          <Button icon={Send} loading={busy} type="submit">Ask</Button>
        </form>
      </div>
    </Card>
  );
}

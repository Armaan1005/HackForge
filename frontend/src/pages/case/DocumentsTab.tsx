import { FileSearch, ShieldAlert } from 'lucide-react';
import { Fragment, type ReactNode } from 'react';
import { Banner, Button, Card, Cite, ErrorState, Skeleton, SourceBadge } from '../../components/ui';
import { ai } from '../../lib/api';
import { pct } from '../../lib/format';
import { useAsync } from '../../lib/hooks';
import type { CaseDetail, Flag } from '../../lib/types';

const CHECK_LABEL: Record<string, string> = {
  inserted_content: 'Inserted content', unlinked_author: 'Unlinked author', phantom_result: 'Phantom result',
  timeline_conflict: 'Timeline conflict', procedure_absent: 'Billed procedure absent', templated_values: 'Templated values',
  style_shift: 'Style shift', signature_reuse: 'Signature reuse', prompt_injection: 'Prompt injection', other: 'Other',
};
const INJ = /(ignore (all |any )?(previous|prior|above)|system (note|prompt|message)[^.]*|note to (the )?(ai|reviewer|model)[^.]*|ai reviewer[^.]*|mark (this|the)? ?(claim|case|record)? ?as (cleared|verified|approved|legitimate))/i;

function highlight(text: string, hasInjection: boolean): ReactNode {
  if (!hasInjection) return text;
  const m = text.match(INJ);
  if (!m || m.index == null) return text;
  // extend the mark to the end of the sentence containing the injection
  const start = text.lastIndexOf('.', m.index) + 1;
  const endDot = text.indexOf('.', m.index + m[0].length);
  const end = endDot === -1 ? text.length : endDot + 1;
  return <>{text.slice(0, start)}<mark className="inj" title="Instruction aimed at an AI reviewer. Axon ignored it.">{text.slice(start, end)}</mark>{text.slice(end)}</>;
}

function FlagRow({ f }: { f: Flag }) {
  return (
    <div className="row-nw" style={{ alignItems: 'flex-start', gap: 8 }}>
      <span className={`chip ${f.check === 'prompt_injection' ? 'chip-warn' : 'chip-bad'}`}><ShieldAlert size={12} />{CHECK_LABEL[f.check] ?? f.check}</span>
      <div className="small" style={{ flex: 1 }}>
        {f.observation}
        {f.evidence_ids.map(id => <Cite key={id} id={id} />)}
        <div className="row xs faint" style={{ marginTop: 3, gap: 6 }}><SourceBadge source={f.source} /><span>{f.label}</span>{f.source === 'ai' && <span>· confidence {pct(f.confidence)}</span>}</div>
      </div>
    </div>
  );
}

export function DocumentsTab({ k }: { k: CaseDetail }) {
  const fx = useAsync(() => ai.forensics(k.case_id), [k.case_id]);
  if (fx.error) return <ErrorState error={new Error(`Document Forensics needs the Part B backend on :8000 (${fx.error.message}).`)} onRetry={fx.reload} />;
  if (!fx.data) return <div className="stack"><Banner icon={FileSearch}>Cross-checking records against claims, referrals and timestamps…</Banner><Skeleton h={340} /></div>;

  return (
    <div className="stack">
      <Banner>
        Generative AI can fabricate or insert content into real records. Axon checks each record against the payer's own data.
        <b> Code-verified</b> flags are field mismatches; <b>AI-observed</b> flags need a human to verify. <b>Neither changes the risk score.</b>
      </Banner>
      {fx.data.injection_detected && (
        <Banner tone="warn" icon={ShieldAlert}><b>Prompt injection detected.</b> A record contains text addressed to an AI reviewer. Axon treated it as data, ignored it, and flagged the record as possibly tampered.</Banner>
      )}
      {fx.data.documents.map(d => {
        const doc = d.document;
        const bySection = (sid: string) => d.integrity_flags.filter(f => f.section_id === sid);
        const general = d.integrity_flags.filter(f => !doc.sections.some(s => s.section_id === f.section_id));
        return (
          <Card key={d.document_id} title={<>{d.document_id} · {doc.doc_type.replace(/_/g, ' ')}</>} icon={FileSearch}
            action={<div className="row"><SourceBadge source={d.source} /><span className="chip">{d.integrity_flags.length} flags</span></div>}>
            <div className="kv" style={{ marginBottom: 14 }}>
              <dt>Record author</dt><dd className="mono">{doc.author_provider_id}</dd>
              <dt>Member</dt><dd className="mono">{doc.member_id}</dd>
              <dt>Claims</dt><dd className="mono">{doc.claim_ids.join(', ')}</dd>
              <dt>Service date</dt><dd>{doc.claim_service_date ?? '—'}</dd>
              <dt>Claim submitted</dt><dd>{doc.claim_submitted_at ?? '—'}</dd>
              <dt>Record created</dt><dd style={{ color: doc.claim_submitted_at && doc.created_at.slice(0, 10) > doc.claim_submitted_at ? 'var(--bad-text)' : undefined }}>{doc.created_at.replace('T', ' ')}</dd>
              {doc.billed_procedures?.map(p => <Fragment key={p.code}><dt>Billed</dt><dd>{p.code} · {p.description}</dd></Fragment>)}
            </div>
            <div className="grid-2" style={{ alignItems: 'start' }}>
              <div className="stack-sm">
                {doc.sections.map(s => {
                  const flags = bySection(s.section_id);
                  const inj = flags.some(f => f.check === 'prompt_injection');
                  return (
                    <div key={s.section_id} className={`doc-section ${flags.length ? 'flagged' : ''} ${inj ? 'injected' : ''}`}>
                      <div className="row-nw between xs faint"><span className="strong" style={{ color: 'var(--text)' }}>{s.section_id} · {s.heading}</span><span className="mono">{s.author_provider_id} · {s.created_at.replace('T', ' ')}</span></div>
                      <div className="small" style={{ marginTop: 6 }}>{highlight(s.text, inj)}</div>
                    </div>
                  );
                })}
                {doc.scan_url && <img src={doc.scan_url} alt={`Scan of ${d.document_id}`} style={{ width: '100%', borderRadius: 12, border: '1px solid var(--line)' }} />}
              </div>
              <div className="stack">
                {doc.sections.map(s => bySection(s.section_id).length > 0 && (
                  <div key={s.section_id} className="stack-sm">
                    <span className="xs faint strong">{s.section_id} · {s.heading}</span>
                    {bySection(s.section_id).map(f => <FlagRow key={f.flag_id} f={f} />)}
                  </div>
                ))}
                {general.length > 0 && <div className="stack-sm"><span className="xs faint strong">Whole record</span>{general.map(f => <FlagRow key={f.flag_id} f={f} />)}</div>}
                {d.integrity_flags.length === 0 && <p className="small muted">No integrity issues found.</p>}
                <p className="xs muted">{d.overall_note}</p>
              </div>
            </div>
          </Card>
        );
      })}
      <div><Button size="sm" variant="ghost" onClick={fx.reload}>Re-run forensics</Button></div>
    </div>
  );
}

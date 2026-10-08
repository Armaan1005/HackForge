import type { ReactNode } from 'react';
import { Icon } from '../../components/Icon';
import { Card, Cite, ErrorState, Note, Skeleton } from '../../components/ui';
import { ai } from '../../lib/api';
import { pct } from '../../lib/format';
import { useAsync } from '../../lib/hooks';
import type { CaseDetail, Flag } from '../../lib/types';

const CHECK_LABEL: Record<string, string> = {
  inserted_content: 'Looks inserted', unlinked_author: 'Author has no link to this patient', phantom_result: 'Result for a test never ordered',
  timeline_conflict: 'Written after the claim', procedure_absent: 'Billed procedure not described', templated_values: 'Copy-paste values',
  style_shift: 'Different writing style', signature_reuse: 'Reused signature', prompt_injection: 'Instruction aimed at an AI', other: 'Other',
};
const INJ = /(ignore (all |any )?(previous|prior|above)|system (note|prompt|message)[^.]*|note to (the )?(ai|reviewer|model)[^.]*|ai reviewer[^.]*|mark (this|the)? ?(claim|case|record)? ?as (cleared|verified|approved|legitimate))/i;

function highlight(text: string, on: boolean): ReactNode {
  const m = on ? text.match(INJ) : null;
  if (!m || m.index == null) return text;
  const start = text.lastIndexOf('.', m.index) + 1;
  const endDot = text.indexOf('.', m.index + m[0].length);
  const end = endDot === -1 ? text.length : endDot + 1;
  return <>{text.slice(0, start)}<mark className="inj" title="Ignored by Axon">{text.slice(start, end)}</mark>{text.slice(end)}</>;
}

function FlagRow({ f }: { f: Flag }) {
  return (
    <div className="row-nw" style={{ alignItems: 'flex-start' }}>
      <span className={`row-icon ${f.check === 'prompt_injection' ? 'warn' : 'bad'}`}><Icon name={f.check === 'prompt_injection' ? 'ai' : 'alert'} size={14} /></span>
      <div className="small" style={{ flex: 1 }}>
        <b>{CHECK_LABEL[f.check] ?? f.check}</b>
        <div className="muted">{f.observation}{f.evidence_ids.map(id => <Cite key={id} id={id} />)}</div>
        <div className="xs faint" style={{ marginTop: 2 }}>{f.source === 'code' ? 'Checked against claims data' : `Spotted by AI · ${pct(f.confidence)} sure · needs a person to verify`}</div>
      </div>
    </div>
  );
}

export function DocumentsTab({ k }: { k: CaseDetail }) {
  const fx = useAsync(() => ai.forensics(k.case_id), [k.case_id]);
  if (fx.error) return <ErrorState error={new Error(`Couldn't reach the AI service (${fx.error.message}).`)} onRetry={fx.reload} />;
  if (!fx.data) return <Skeleton h={360} />;

  return (
    <div className="stack-lg">
      {fx.data.injection_detected
        ? <Note tone="warn" icon="ai"><b>A record tried to instruct the AI reviewer.</b> Axon treated it as text, ignored it and flagged the record.</Note>
        : <Note>Each record is checked against claims, referrals and timestamps. These flags never change the risk score.</Note>}
      {fx.data.documents.map(d => {
        const doc = d.document;
        const flagsFor = (sid: string) => d.integrity_flags.filter(f => f.section_id === sid);
        const general = d.integrity_flags.filter(f => !doc.sections.some(s => s.section_id === f.section_id));
        const late = doc.claim_submitted_at && doc.created_at.slice(0, 10) > doc.claim_submitted_at;
        return (
          <div key={d.document_id} className="cand-bottom">
            <Card>
              <div className="card-title"><span className="row-icon"><Icon name="document-text" size={15} /></span><h2>{doc.doc_type.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())}</h2><span className="spacer" /><span className="ev-id">{d.document_id}</span></div>
              <div className="stack">
                {doc.sections.map(s => {
                  const fl = flagsFor(s.section_id);
                  return (
                    <div key={s.section_id} className={`doc-section ${fl.length ? 'flagged' : ''}`}>
                      <div className="row-flex xs faint" style={{ justifyContent: 'space-between' }}><b style={{ color: 'var(--text)', fontSize: '.88rem' }}>{s.heading}</b><span>{s.author_provider_id} · {s.created_at.slice(0, 10)}</span></div>
                      <p className="small" style={{ marginTop: 6 }}>{highlight(s.text, fl.some(f => f.check === 'prompt_injection'))}</p>
                    </div>
                  );
                })}
              </div>
            </Card>
            <div className="stack-lg">
              <Card>
                <dl className="facts">
                  <div><dt>Written by</dt><dd>{doc.author_provider_id}</dd></div>
                  <div><dt>Claim sent</dt><dd>{doc.claim_submitted_at ?? '—'}</dd></div>
                  <div><dt>Record made</dt><dd style={{ color: late ? 'var(--bad)' : undefined }}>{doc.created_at.slice(0, 10)}{late ? ' · after the claim' : ''}</dd></div>
                </dl>
              </Card>
              <Card>
                <h2 style={{ marginBottom: 14 }}>{d.integrity_flags.length ? `${d.integrity_flags.length} things to check` : 'Nothing looks off'}</h2>
                <div className="stack">
                  {doc.sections.flatMap(s => flagsFor(s.section_id)).map(f => <FlagRow key={f.flag_id} f={f} />)}
                  {general.map(f => <FlagRow key={f.flag_id} f={f} />)}
                </div>
              </Card>
            </div>
          </div>
        );
      })}
    </div>
  );
}

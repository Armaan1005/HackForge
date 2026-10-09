import { useMemo, useState, type ReactNode } from 'react';
import { Icon, type IconName } from '../../components/Icon';
import { Card, Cite, ErrorState, Note, Section, Segmented, Sheet, Skeleton } from '../../components/ui';
import { ai } from '../../lib/api';
import { pct } from '../../lib/format';
import { useAsync } from '../../lib/hooks';
import type { CaseDetail, Flag, Forensics } from '../../lib/types';

type DocResult = Forensics['documents'][number];

const CHECK_LABEL: Record<string, string> = {
  inserted_content: 'Looks inserted', unlinked_author: 'Author has no link to this patient', phantom_result: 'Result for a test never ordered',
  timeline_conflict: 'Dates don’t match the claim', procedure_absent: 'Billed procedure not described', templated_values: 'Copy-paste values',
  style_shift: 'Different writing style', signature_reuse: 'Reused signature', prompt_injection: 'Instruction aimed at an AI', other: 'Other',
};
const TYPE: Record<string, { label: string; icon: IconName }> = {
  progress_note: { label: 'Progress notes', icon: 'document-text' },
  consult_note: { label: 'Consult notes', icon: 'stethoscope' },
  lab_report: { label: 'Lab reports', icon: 'lab' },
  operative_note: { label: 'Operative notes', icon: 'syringe' },
  discharge_summary: { label: 'Discharge summaries', icon: 'bed' },
  referral_letter: { label: 'Referral letters', icon: 'chain-link' },
  consent_form: { label: 'Consent forms', icon: 'decision' },
};
const ORDER = Object.keys(TYPE);
const INJ = /(ignore (all |any )?(previous|prior|above)|system (note|prompt|message)[^.]*|note to (the )?(ai|reviewer|model)[^.]*|ai reviewer[^.]*|mark (this|the)? ?(claim|case|record)? ?as (cleared|verified|approved|legitimate))/i;
const fmtDate = (d: string) => new Date(`${d.slice(0, 10)}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });

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
        <div className="xs faint" style={{ marginTop: 2 }}>{f.source === 'code' ? 'Checked against claims data' : `Spotted by AI · ${pct(f.confidence)} sure · a person should verify`}</div>
      </div>
    </div>
  );
}

/** One record, opened in a sheet: the text on the left, what was found on the right. */
function RecordSheet({ d, onClose }: { d: DocResult | null; onClose: () => void }) {
  if (!d) return <Sheet open={false} onClose={onClose} title="">{null}</Sheet>;
  const doc = d.document;
  const late = doc.claim_submitted_at && doc.created_at.slice(0, 10) > doc.claim_submitted_at;
  const flagged = (sid: string) => d.integrity_flags.filter(f => f.section_id === sid);
  return (
    <Sheet open onClose={onClose} title={`${TYPE[doc.doc_type]?.label.replace(/s$/, '') ?? doc.doc_type} · ${d.document_id}`} wide>
      <div className="row-flex small muted" style={{ marginBottom: 16, gap: 16 }}>
        <span>Written by <b style={{ color: 'var(--text)' }}>{doc.author_provider_id}</b></span>
        <span>Claim sent <b style={{ color: 'var(--text)' }}>{doc.claim_submitted_at ? fmtDate(doc.claim_submitted_at) : '—'}</b></span>
        <span>Record made <b style={{ color: late ? 'var(--bad)' : 'var(--text)' }}>{fmtDate(doc.created_at)}{late ? ' (after the claim)' : ''}</b></span>
        {doc.scan_url && <a href={doc.scan_url} target="_blank" rel="noreferrer"><Icon name="attachment" size={13} className="inline" /> Open scan</a>}
      </div>
      <div className="cand-bottom" style={{ gridTemplateColumns: 'minmax(0, 1.4fr) minmax(0, 1fr)' }}>
        <div className="stack">
          {doc.sections.map(s => {
            const fl = flagged(s.section_id);
            return (
              <div key={s.section_id} className={`doc-section ${fl.length ? 'flagged' : ''}`}>
                <div className="row-flex xs faint" style={{ justifyContent: 'space-between' }}><b style={{ color: 'var(--text)', fontSize: '.88rem' }}>{s.heading}</b><span>{s.author_provider_id} · {fmtDate(s.created_at)}</span></div>
                <p className="small" style={{ marginTop: 6 }}>{highlight(s.text, fl.some(f => f.check === 'prompt_injection'))}</p>
              </div>
            );
          })}
        </div>
        <div className="stack">
          <h3>{d.integrity_flags.length ? `${d.integrity_flags.length} thing${d.integrity_flags.length > 1 ? 's' : ''} to check` : 'Nothing looks off'}</h3>
          {d.integrity_flags.map(f => <FlagRow key={f.flag_id} f={f} />)}
          {d.source === 'code_only' && <p className="xs faint">Checked by code only. AI review is saved for the most important records.</p>}
        </div>
      </div>
    </Sheet>
  );
}

export function DocumentsTab({ k }: { k: CaseDetail }) {
  const fx = useAsync(() => ai.forensics(k.case_id), [k.case_id]);
  const [view, setView] = useState<'flagged' | 'all'>('flagged');
  const [open, setOpen] = useState<DocResult | null>(null);

  const groups = useMemo(() => {
    const docs = fx.data?.documents ?? [];
    const shown = view === 'flagged' ? docs.filter(d => d.integrity_flags.length) : docs;
    const by = new Map<string, DocResult[]>();
    for (const d of shown) by.set(d.document.doc_type, [...(by.get(d.document.doc_type) ?? []), d]);
    return [...by.entries()]
      .sort(([a], [b]) => (ORDER.indexOf(a) + 99 * +(ORDER.indexOf(a) < 0)) - (ORDER.indexOf(b) + 99 * +(ORDER.indexOf(b) < 0)))
      .map(([type, list]) => [type, list.sort((x, y) => y.integrity_flags.length - x.integrity_flags.length)] as const);
  }, [fx.data, view]);

  if (fx.error) return <ErrorState error={new Error(`Couldn't reach the AI service (${fx.error.message}).`)} onRetry={fx.reload} />;
  if (!fx.data) return <Card><div className="row-flex"><Skeleton h={18} style={{ width: 220 }} /><span className="small muted">Checking records against claims, referrals and dates…</span></div><Skeleton h={260} style={{ marginTop: 16 }} /></Card>;

  const docs = fx.data.documents;
  const flagged = docs.filter(d => d.integrity_flags.length).length;

  // Some cases have no medical records at all (e.g. ambulance trips: there are no trip sheets in the data).
  if (docs.length === 0) {
    const NOUN: Record<string, string> = { ambulance: 'ambulance trips', professional: 'clinic visits', pharmacy: 'pharmacy fills', lab: 'lab tests',
      facility: 'facility stays', behavioral_health: 'behavioural health sessions', home_health: 'home health visits', dme: 'equipment rentals' };
    const types = Object.keys(k.claims_summary.service_types ?? {}).map(t => NOUN[t] ?? t.replace(/_/g, ' '));
    return (
      <Card>
        <h2>No medical records linked to this case</h2>
        <p className="muted" style={{ marginTop: 6, maxWidth: 640 }}>
          The {k.claims_summary.claim_count} claims here are {types.length ? types.join(' and ') : 'services'} with no notes, reports or scans attached,
          so there is nothing for the records check to read. The evidence comes from the claims themselves; see the Evidence tab.
        </p>
        {k.missing_documents.length > 0 && <p className="small" style={{ marginTop: 10 }}>Missing: {k.missing_documents.map(m => `${m.doc_type.replace(/_/g, ' ')} (${m.claim_count} claims)`).join(', ')}</p>}
      </Card>
    );
  }

  return (
    <div className="cand-bottom flat">
      <div>
        <div className="row-flex" style={{ marginBottom: 14 }}>
          <Segmented size="sm" label="Show" value={view} onChange={setView}
            options={[{ value: 'flagged', label: `Needs a look · ${flagged}` }, { value: 'all', label: `All records · ${docs.length}` }]} />
        </div>
        {groups.length === 0 && <Card><p className="muted">No records need a look. Switch to “All records” to browse them.</p></Card>}
        {groups.map(([type, list]) => (
          <Section key={type} title={`${TYPE[type]?.label ?? type} · ${list.length}`}>
            {list.map(d => {
              const n = d.integrity_flags.length;
              const inj = d.integrity_flags.some(f => f.check === 'prompt_injection');
              const first = d.integrity_flags[0];
              return (
                <div key={d.document_id} className="row clickable" onClick={() => setOpen(d)} role="button" tabIndex={0} onKeyDown={e => e.key === 'Enter' && setOpen(d)}>
                  <span className={`row-icon ${n ? (inj ? 'warn' : 'bad') : ''}`}><Icon name={d.document.format === 'scan' ? 'attachment' : TYPE[type]?.icon ?? 'document'} size={15} /></span>
                  <div className="row-text">
                    <span className="row-label">{fmtDate(d.document.created_at)} <span className="faint small">· {d.document_id}</span></span>
                    <span className="row-desc clamp-1">{first ? (CHECK_LABEL[first.check] ?? first.check) + (n > 1 ? ` and ${n - 1} more` : '') : `By ${d.document.author_provider_id}${d.document.format === 'scan' ? ' · scanned' : ''}`}</span>
                  </div>
                  {n ? <span className={`review-pill ${inj ? 'review-pending' : ''}`} style={inj ? undefined : { background: 'color-mix(in srgb, var(--bad) 12%, transparent)', color: 'var(--bad)' }}>{n} to check</span>
                    : <span className="review-pill review-done"><Icon name="accept" size={11} />Looks fine</span>}
                  <Icon name="slim-arrow-right" size={14} className="muted" />
                </div>
              );
            })}
          </Section>
        ))}
      </div>

      <div className="stack-lg panel-stack">
        <div className="stats" style={{ gridTemplateColumns: '1fr 1fr' }}>
          <div className="stat"><b>{docs.length}</b><span>records checked</span></div>
          <div className={`stat ${flagged ? 'warn' : ''}`}><b>{flagged}</b><span>need a look</span></div>
        </div>
        {fx.data.injection_detected && <Note tone="warn" icon="ai"><b>A record tried to instruct the AI.</b> Axon treated it as text, ignored it and flagged it.</Note>}
        <Note>Records are checked against claims, referrals and dates. These checks never change the risk score.</Note>
      </div>

      <RecordSheet d={open} onClose={() => setOpen(null)} />
    </div>
  );
}

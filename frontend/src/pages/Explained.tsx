import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { Mascot } from '../components/Mascot';
import { Bar, Card, Cite, ErrorState, Note, PageHeader, Section, Sheet, Skeleton } from '../components/ui';
import { ai, api } from '../lib/api';
import { num } from '../lib/format';
import { useAsync } from '../lib/hooks';

const EX_LABEL: Record<string, string> = {
  EX1_sole_provider: 'Only provider nearby', EX2_case_mix_adjusted: 'Sicker patients', EX3_corrected_claim: 'Corrected claim',
  EX4_event_or_seasonal: 'Event or season', EX5_chronic_schedule: 'Regular treatment', EX6_network_explained: 'Normal group practice',
};
/** What each clearing rule checks, and the rulebook page it corresponds to. */
const EX_RULE: Record<string, { what: string; rule: string }> = {
  EX1_sole_provider: { what: 'The only provider of its kind for a large area, so high volume is expected. It is compared per population served, not with city peers.', rule: 'POL-027' },
  EX2_case_mix_adjusted: { what: 'Its patients are sicker than its peers’. After adjusting for that, its usage falls below the level that needs review.', rule: 'POL-005' },
  EX3_corrected_claim: { what: 'A corrected or replacement claim, not a second bill for the same service.', rule: 'POL-002' },
  EX4_event_or_seasonal: { what: 'Many unrelated providers in the same area spiked at the same time. That points to an event or season, not one provider.', rule: 'POL-030' },
  EX5_chronic_schedule: { what: 'Visits follow a recognised treatment schedule, such as dialysis about three times a week.', rule: 'POL-028' },
  EX6_network_explained: { what: 'The shared ownership looks like a normal group practice, with no billing anomaly alongside it.', rule: 'POL-029' },
};
const SIGNAL = (s: string) => {
  const [layer, ...rest] = s.split('.');
  const name = rest.join(' ').replace(/^R\d+_/, '').replace(/^robust_z /, '').replace(/_/g, ' ').replace(/\bem\b/, 'E&M');
  if (s === 'anomaly.isolation_forest') return 'Overall billing profile unusual';
  return `${{ rule: 'Rule', anomaly: 'Unusual vs peers', temporal: 'Timing', graph: 'Network' }[layer] ?? layer}: ${name}`;
};
const fact = (v: unknown) => (Array.isArray(v) ? v.join('–') : typeof v === 'number' ? num(v, 2) : String(v));

type Alert = Awaited<ReturnType<typeof api.cleared>>['items'][number];

export function Explained() {
  const cl = useAsync(() => api.cleared(50), []);
  const ov = useAsync(() => api.overview(), []);
  const tr = useAsync(() => api.trust(), []);
  const [lines, setLines] = useState<Record<string, string>>({});
  const [open, setOpen] = useState<Alert | null>(null);
  useEffect(() => {
    if (cl.data) ai.explainCleared(50).then(r => setLines(Object.fromEntries(r.items.map(i => [i.alert_id, i.text])))).catch(() => {});
  }, [cl.data]);
  if (cl.error) return <ErrorState error={cl.error} onRetry={cl.reload} />;
  const reasons = ov.data ? Object.entries(ov.data.exoneration_by_reason) as [string, number][] : [];
  const maxR = Math.max(1, ...reasons.map(([, v]) => v));

  return (
    <>
      <PageHeader eyebrow="Explained" title={cl.data ? `${num(cl.data.total)} alerts you don't need to look at` : '…'}
        subtitle="Raised by the engine, then cleared because an innocent explanation fit the facts. Tap one to see why."
        actions={<Mascot size={80} mood="happy" />} />

      <div className="home-grid">
        <div>
          {!cl.data ? <Skeleton h={320} /> : (
            <Section title="Recently cleared">
              {cl.data.items.map(a => (
                <div key={a.alert_id} className="row clickable" role="button" tabIndex={0} onClick={() => setOpen(a)} onKeyDown={e => e.key === 'Enter' && setOpen(a)}>
                  <span className="row-icon"><Icon name="accept" size={15} /></span>
                  <div className="row-text">
                    <span className="row-label">{a.entity_name}</span>
                    <span className="row-desc clamp-1">{lines[a.alert_id] ?? EX_RULE[a.exoneration_code]?.what ?? ''}</span>
                  </div>
                  <span className="chip chip-static">{EX_LABEL[a.exoneration_code] ?? a.exoneration_code}</span>
                  <Icon name="slim-arrow-right" size={14} className="muted" />
                </div>
              ))}
            </Section>
          )}
        </div>
        <div className="stack-lg">
          <Card>
            <h2 style={{ marginBottom: 14 }}>Why they were cleared</h2>
            <div className="stack">{reasons.map(([k, v]) => <Bar key={k} label={EX_LABEL[k] ?? k} value={v} max={maxR} right={num(v)} />)}</div>
          </Card>
          <Note>Hard signals are never cleared: billing after death, more than 24 hours in a day, or ambulance miles far beyond the map distance.</Note>
          {tr.data && <Note tone={tr.data.exoneration.planted_fraud_wrongly_cleared ? 'warn' : 'good'} icon="complete">
            <b>{tr.data.exoneration.planted_fraud_wrongly_cleared}</b> of the planted fraud cases were cleared by mistake.
          </Note>}
        </div>
      </div>

      <AlertSheet a={open} line={open ? lines[open.alert_id] : undefined} onClose={() => setOpen(null)} />
    </>
  );
}

function AlertSheet({ a, line, onClose }: { a: Alert | null; line?: string; onClose: () => void }) {
  const ex = a ? EX_RULE[a.exoneration_code] : undefined;
  return (
    <Sheet open={!!a} onClose={onClose} title={a ? a.entity_name : ''} wide>
      {a && (
        <div className="stack-lg">
          <div className="row-flex small muted" style={{ gap: 10 }}>
            <span className="chip chip-static">{EX_LABEL[a.exoneration_code] ?? a.exoneration_code}</span>
            <span>{a.alert_id} · {a.entity_type} {a.entity_id}</span>
          </div>

          <div className="alert-cols">
            <div>
              <p className="eyebrow">Why it was cleared</p>
              {line && <p style={{ marginTop: 4 }}>{line}</p>}
              {ex && <p className="small muted" style={{ marginTop: 6 }}>{ex.what}</p>}
              <dl className="facts" style={{ marginTop: 12 }}>
                {Object.entries(a.facts).map(([k, v]) => (
                  <div key={k}><dt>{k.replace(/_/g, ' ')}</dt><dd><b>{fact(v)}</b></dd></div>
                ))}
              </dl>
            </div>

            <div className="stack-lg">
              <div>
                <p className="eyebrow">What raised it</p>
                <p className="small muted" style={{ marginTop: 4 }}>Risk {a.original_risk} before clearing</p>
                <ul className="list-check" style={{ marginTop: 8 }}>
                  {a.triggered_by.map(s => <li key={s}><Icon name="inspect" size={14} /><span className="small">{SIGNAL(s)}</span></li>)}
                </ul>
              </div>
              <div className="row-flex" style={{ gap: 6 }}>{a.evidence_ids.map(id => <Cite key={id} id={id} />)}</div>
              {ex && <Link to={`/rulebook?rule=${ex.rule}`} className="btn btn-secondary btn-sm" style={{ justifySelf: 'start', alignSelf: 'flex-start' }}><Icon name="course-book" size={14} />Rule {ex.rule} in the rulebook</Link>}
            </div>
          </div>
        </div>
      )}
    </Sheet>
  );
}

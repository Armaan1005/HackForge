import { useEffect, useState } from 'react';
import { Icon } from '../components/Icon';
import { Mascot } from '../components/Mascot';
import { Bar, Card, ErrorState, Note, PageHeader, Section, Skeleton } from '../components/ui';
import { ai, api } from '../lib/api';
import { num } from '../lib/format';
import { useAsync } from '../lib/hooks';

const EX_LABEL: Record<string, string> = {
  EX1_sole_provider: 'Only provider nearby', EX2_case_mix_adjusted: 'Sicker patients', EX3_corrected_claim: 'Corrected claim',
  EX4_event_or_seasonal: 'Event or season', EX5_chronic_schedule: 'Regular treatment', EX6_network_explained: 'Normal group practice',
};

export function Explained() {
  const cl = useAsync(() => api.cleared(50), []);
  const ov = useAsync(() => api.overview(), []);
  const tr = useAsync(() => api.trust(), []);
  const [lines, setLines] = useState<Record<string, string>>({});
  useEffect(() => {
    if (cl.data) ai.explainCleared(20).then(r => setLines(Object.fromEntries(r.items.map(i => [i.alert_id, i.text])))).catch(() => {});
  }, [cl.data]);
  if (cl.error) return <ErrorState error={cl.error} onRetry={cl.reload} />;
  const reasons = ov.data ? Object.entries(ov.data.exoneration_by_reason) as [string, number][] : [];
  const maxR = Math.max(1, ...reasons.map(([, v]) => v));

  return (
    <>
      <PageHeader eyebrow="Explained" title={cl.data ? `${num(cl.data.total)} alerts you don't need to look at` : '…'}
        subtitle="Cleared before they reached anyone, with the facts behind each."
        actions={<Mascot size={80} mood="happy" />} />

      <div className="home-grid">
        <div>
          {!cl.data ? <Skeleton h={320} /> : (
            <Section title="Recently cleared">
              {cl.data.items.map(a => (
                <div key={a.alert_id} className="row" title={Object.entries(a.facts).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join('–') : v}`).join('\n')}>
                  <span className="row-icon"><Icon name="accept" size={15} /></span>
                  <div className="row-text">
                    <span className="row-label">{a.entity_name}</span>
                    <span className="row-desc">{lines[a.alert_id] ?? 'Explaining…'}</span>
                  </div>
                  <span className="chip chip-static">{EX_LABEL[a.exoneration_code] ?? a.exoneration_code}</span>
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
    </>
  );
}

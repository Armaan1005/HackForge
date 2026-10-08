import { AreaTrend, weekly } from '../../components/AreaTrend';
import { Card, Cite, Skeleton } from '../../components/ui';
import { api } from '../../lib/api';
import { useAsync } from '../../lib/hooks';
import type { CaseDetail } from '../../lib/types';

const SIM_TODAY = '2026-10-01';
const fmt = (d: string) => new Date(`${d}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });

export function TimelineTab({ k }: { k: CaseDetail }) {
  const cl = useAsync(() => api.claims(k.case_id), [k.case_id]);
  return (
    <div className="stack-lg">
    {!cl.data ? <Skeleton h={340} /> : cl.data.claims.length > 0 && (
      <AreaTrend title="Billed per week" today={SIM_TODAY} height={220}
        description={`${cl.data.total} claims in this case. Amber has been paid out; green is still pending and can be held.`}
        data={weekly(cl.data.claims)}
        source={`Axon engine, claims of ${k.case_id} (service_date, billed_amount, payment_status) · synthetic data`} />
    )}
    <Card style={{ maxWidth: 820 }}>
      <h2 style={{ marginBottom: 18 }}>How this case unfolded</h2>
      <div className="tl">
        {k.timeline.map(t => (
          <div key={t.date + t.event_type} className={`tl-item ${t.date > SIM_TODAY ? 'future' : ''}`}>
            <div className="small muted">{fmt(t.date)}{t.date > SIM_TODAY ? ' · coming up' : ''}</div>
            <div style={{ fontWeight: 550 }}>{t.description}{t.evidence_ids.map(id => <Cite key={id} id={id} />)}</div>
          </div>
        ))}
      </div>
    </Card>
    </div>
  );
}

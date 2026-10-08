import { CheckCircle2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { BarList } from '../components/charts';
import { Card, ErrorState, Skeleton } from '../components/ui';
import { ai, api } from '../lib/api';
import { num } from '../lib/format';
import { useAsync } from '../lib/hooks';

const EX_LABEL: Record<string, string> = {
  EX1_sole_provider: 'Sole provider in area', EX2_case_mix_adjusted: 'Sicker patients', EX3_corrected_claim: 'Corrected claim',
  EX4_event_or_seasonal: 'Event or season', EX5_chronic_schedule: 'Chronic treatment', EX6_network_explained: 'Normal group practice',
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

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <div className="eyebrow">Explained</div>
          <h1>{cl.data ? `${num(cl.data.total)} alerts cleared by code` : '…'}</h1>
          <p className="subtitle">Hard signals are never cleared · {tr.data ? tr.data.exoneration.planted_fraud_wrongly_cleared : '…'} planted fraud cleared by mistake</p>
        </div>
      </div>

      <div className="grid-main">
        <Card className="card-flush">
          {!cl.data ? <Skeleton h={300} style={{ margin: 16 }} /> : (
            <div className="list">
              {cl.data.items.map(a => (
                <div key={a.alert_id} className="list-row" style={{ alignItems: 'flex-start' }}
                  title={Object.entries(a.facts).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join('–') : v}`).join('\n')}>
                  <CheckCircle2 size={18} style={{ color: 'var(--good)', flex: 'none', marginTop: 2 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="row between"><b>{a.entity_name}</b><span className="chip">{EX_LABEL[a.exoneration_code] ?? a.exoneration_code}</span></div>
                    <div className="small muted" style={{ marginTop: 3 }}>{lines[a.alert_id] ?? '…'}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card title="By reason">
          {ov.data ? <BarList rows={Object.entries(ov.data.exoneration_by_reason).map(([k, v]) => ({ label: EX_LABEL[k] ?? k, value: v as number }))} /> : <Skeleton h={160} />}
        </Card>
      </div>
    </div>
  );
}

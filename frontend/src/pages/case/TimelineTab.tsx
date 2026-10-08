import { Card, Cite } from '../../components/ui';
import type { CaseDetail } from '../../lib/types';

const SIM_TODAY = '2026-10-01';
const fmt = (d: string) => new Date(`${d}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });

export function TimelineTab({ k }: { k: CaseDetail }) {
  return (
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
  );
}

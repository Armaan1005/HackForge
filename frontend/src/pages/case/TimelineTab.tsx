import { Card, Cite } from '../../components/ui';
import type { CaseDetail } from '../../lib/types';

const SIM_TODAY = '2026-10-01';

export function TimelineTab({ k }: { k: CaseDetail }) {
  return (
    <Card title="Timeline" action={<span className="xs faint">simulation date {SIM_TODAY} · dashed = upcoming</span>}>
      <div className="timeline" style={{ marginTop: 6 }}>
        {k.timeline.map(t => (
          <div key={t.date + t.event_type} className={`tl-item ${t.date > SIM_TODAY ? 'future' : ''}`}>
            <div className="row-nw" style={{ gap: 10 }}>
              <span className="strong tabular nowrap">{t.date}</span>
              <span className="chip">{t.event_type.replace(/_/g, ' ')}</span>
            </div>
            <div className="small" style={{ marginTop: 4 }}>
              {t.description}
              {t.evidence_ids.map(id => <Cite key={id} id={id} />)}
            </div>
            {t.claim_ids.length > 0 && <div className="xs faint mono" style={{ marginTop: 2 }}>{t.claim_ids.join(', ')}</div>}
          </div>
        ))}
      </div>
    </Card>
  );
}

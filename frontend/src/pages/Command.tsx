import { AlarmClock, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Funnel } from '../components/charts';
import { Button, Card, ErrorState, RiskRing, Skeleton, StatusPill } from '../components/ui';
import { api } from '../lib/api';
import { inr, num } from '../lib/format';
import { useAsync } from '../lib/hooks';

export function Command() {
  const nav = useNavigate();
  const ov = useAsync(() => api.overview(), []);
  const q = useAsync(() => api.queue(40, 30), []);
  if (ov.error) return <ErrorState error={ov.error} onRetry={ov.reload} />;

  const f = ov.data?.funnel, queue = q.data;
  const plan = queue?.cases.filter(c => c.selected) ?? [];
  const clock = (queue?.cases ?? []).filter(c => c.days_until_release != null && c.days_until_release <= 14)
    .sort((a, b) => (a.days_until_release ?? 99) - (b.days_until_release ?? 99)).slice(0, 4);
  const holds = clock.filter(c => c.hold_recommended);

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <div className="eyebrow">Today · {ov.data?.sim_today ?? '…'}</div>
          <h1>{queue ? `${queue.selected_count} cases worth your team's time` : 'Loading…'}</h1>
          {f && <p className="subtitle">{num(f.alerts)} alerts in, {num(f.explained)} explained away by code.</p>}
        </div>
        <Button icon={ArrowRight} onClick={() => nav('/queue')}>Open queue</Button>
      </div>

      <Card>
        <div className="grid-3">
          <div className="metric"><div className="k">Expected recovery</div><div className="v">{queue ? inr(queue.expected_recovery_selected) : '…'}</div><div className="s">{queue ? `${queue.hours_used} of ${queue.capacity_hours} hours` : ''}</div></div>
          <div className="metric"><div className="k">Per investigator hour</div><div className="v">{queue ? inr(queue.recovery_per_hour) : '…'}</div></div>
          <div className="metric"><div className="k">Payment holds to review</div><div className="v" style={{ color: holds.length ? 'var(--warn-text)' : undefined }}>{queue ? holds.length : '…'}</div></div>
        </div>
      </Card>

      <div className="grid-main">
        <Card title="From alerts to cases">
          {f ? <Funnel stages={[
            { label: 'Claim lines', value: f.claim_lines },
            { label: 'Alerts', value: f.alerts },
            { label: 'Still open', value: f.open_alerts, note: `${num(f.explained)} explained by code` },
            { label: 'Cases', value: f.cases, note: 'Linked alerts grouped' },
            { label: "Today's plan", value: queue?.selected_count ?? f.selected_today },
          ]} /> : <Skeleton h={180} />}
        </Card>

        <Card title="Money clock" action={<span className="xs faint">next 14 days</span>}>
          {!queue ? <Skeleton h={180} /> : (
            <div className="list" style={{ margin: '-4px -20px -20px' }}>
              {clock.map(c => (
                <div key={c.case_id} className="list-row clickable" onClick={() => nav(`/cases/${c.case_id}`)}>
                  <div style={{ width: 34 }} className="strong tabular" >{c.days_until_release}d</div>
                  <div className="clamp-1 small" style={{ flex: 1 }}>{c.title}</div>
                  {c.hold_recommended ? <span className="chip chip-warn"><AlarmClock size={12} />Hold?</span> : <span className="small muted tabular">{inr(c.dollars_at_risk)}</span>}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card title="Today's plan" action={<Button size="sm" variant="ghost" onClick={() => nav('/queue')}>All cases</Button>}>
        {!queue ? <Skeleton h={200} /> : (
          <div className="list" style={{ margin: '-4px -20px -20px' }}>
            {plan.map(c => (
              <div key={c.case_id} className="list-row clickable" onClick={() => nav(`/cases/${c.case_id}`)}>
                <RiskRing value={c.risk} size={38} />
                <div className="clamp-1" style={{ flex: 1 }}><span className="strong">{c.title}</span></div>
                <span className="small muted nowrap">{c.effort_hours}h</span>
                <span className="strong tabular nowrap" style={{ width: 84, textAlign: 'right' }}>{inr(c.expected_recovery)}</span>
                <StatusPill status={c.status} />
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

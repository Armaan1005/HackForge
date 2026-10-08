import { motion } from 'motion/react';
import { useNavigate } from 'react-router-dom';
import { Funnel } from '../components/charts';
import { Icon, type IconName } from '../components/Icon';
import { Mascot } from '../components/Mascot';
import { INVESTIGATOR } from '../components/TopNav';
import { Button, Card, ErrorState, PageHeader, RiskPill, Skeleton, Status } from '../components/ui';
import { api } from '../lib/api';
import { greeting, inr, num, PATTERN_ICON } from '../lib/format';
import { useAsync } from '../lib/hooks';
import { spring } from '../lib/theme';

export function Command() {
  const nav = useNavigate();
  const ov = useAsync(() => api.overview(), []);
  const q = useAsync(() => api.queue(40, 30), []);
  if (ov.error) return <ErrorState error={ov.error} onRetry={ov.reload} />;

  const f = ov.data?.funnel, queue = q.data;
  const plan = queue?.cases.filter(c => c.selected) ?? [];
  const urgent = [...(queue?.cases ?? [])].filter(c => c.hold_recommended).sort((a, b) => (a.days_until_release ?? 99) - (b.days_until_release ?? 99))[0];
  const date = new Date(`${ov.data?.sim_today ?? '2026-10-01'}T09:00:00`).toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' });

  return (
    <>
      <PageHeader eyebrow={date} title={`${greeting()}, ${INVESTIGATOR.name.split(' ')[0]}.`}
        subtitle={f && queue ? `${num(f.alerts)} alerts came in. Axon explained ${num(f.explained)} of them, so ${queue.selected_count} cases are worth your time today.` : undefined}
        actions={<Mascot size={84} mood="watching" />} />

      <div className="home-grid">
        <div className="stack-lg">
          {urgent && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={spring}>
              <Card className="card-accent" interactive onClick={() => nav(`/cases/${urgent.case_id}`)}>
                <div className="next-step">
                  <span className="big-icon"><Icon name="payment-approval" size={26} /></span>
                  <div style={{ flex: 1 }}>
                    <p className="eyebrow" style={{ marginBottom: 2 }}>Your next step</p>
                    <h2>{urgent.title}</h2>
                    <p className="muted small" style={{ marginTop: 4 }}>{inr(urgent.dollars_at_risk)} at stake · payment releases in {urgent.days_until_release} days</p>
                  </div>
                  <Icon name="slim-arrow-right" size={20} className="muted" />
                </div>
              </Card>
            </motion.div>
          )}

          <Card>
            <div className="row-flex" style={{ marginBottom: 6 }}>
              <h2>Today's plan</h2><span className="spacer" />
              <Button variant="ghost" size="sm" iconRight="slim-arrow-right" onClick={() => nav('/queue')}>All cases</Button>
            </div>
            {!queue ? <Skeleton h={220} /> : (
              <div className="timeline">
                {plan.map(c => (
                  <div key={c.case_id} className="timeline-item" style={{ cursor: 'pointer' }} onClick={() => nav(`/cases/${c.case_id}`)}>
                    <span className="row-icon"><Icon name={PATTERN_ICON[c.pattern] ?? 'inspect'} size={15} /></span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <b className="clamp-1" style={{ display: 'block' }}>{c.title}</b>
                      <div className="small muted">{c.effort_hours} hours · {inr(c.expected_recovery)} likely recovered</div>
                    </div>
                    <RiskPill value={c.risk} />
                    <Status value={c.status} />
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="stack-lg">
          <div className="stats" style={{ gridTemplateColumns: '1fr 1fr' }}>
            <div className="stat"><b>{queue ? inr(queue.expected_recovery_selected) : '…'}</b><span>likely recovered today</span></div>
            <div className="stat"><b>{queue ? inr(queue.recovery_per_hour) : '…'}</b><span>per investigator hour</span></div>
          </div>

          <Card>
            <h2 style={{ marginBottom: 14 }}>From alerts to cases</h2>
            {f ? <Funnel stages={[
              { label: 'Claims', value: f.claim_lines },
              { label: 'Alerts', value: f.alerts },
              { label: 'Still open', value: f.open_alerts, note: `${num(f.explained)} explained by code` },
              { label: 'Cases', value: f.cases },
              { label: 'Today', value: queue?.selected_count ?? f.selected_today },
            ]} /> : <Skeleton h={160} />}
          </Card>

          {([
            ['complete', 'Why alerts were cleared', '/explained'],
            ['lab', 'Try to beat the detector', '/twin'],
            ['shield', 'How well Axon works', '/trust'],
          ] as [IconName, string, string][]).map(([icon, label, to]) => (
            <Card key={to} className="card-tight" interactive onClick={() => nav(to)}>
              <div className="row-nw">
                <span className="row-icon"><Icon name={icon} size={16} /></span>
                <b style={{ flex: 1 }}>{label}</b>
                <Icon name="slim-arrow-right" size={16} className="muted" />
              </div>
            </Card>
          ))}
        </div>
      </div>
    </>
  );
}

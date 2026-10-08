import { motion } from 'motion/react';
import { AlarmClock, ArrowRight, Banknote, Clock3, Database, Filter, Gauge, Layers, ShieldCheck, Timer, UserCheck } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { BarList, Funnel } from '../components/charts';
import { Button, Card, ErrorState, RiskRing, Skeleton, Stat, StatusPill, StrengthPill } from '../components/ui';
import { api } from '../lib/api';
import { inr, METHOD_LABEL, num, PATTERN, relDays, titleCase } from '../lib/format';
import { useAsync } from '../lib/hooks';

const EX_LABEL: Record<string, string> = {
  EX1_sole_provider: 'Sole provider in area', EX2_case_mix_adjusted: 'Case-mix adjusted', EX3_corrected_claim: 'Corrected claim',
  EX4_event_or_seasonal: 'Event or seasonal', EX5_chronic_schedule: 'Chronic schedule', EX6_network_explained: 'Network explained',
};

export function Command() {
  const nav = useNavigate();
  const ov = useAsync(() => api.overview(), []);
  const q = useAsync(() => api.queue(40, 30), []);

  if (ov.error) return <ErrorState error={ov.error} onRetry={ov.reload} />;
  const o = ov.data, queue = q.data;
  const f = o?.funnel;
  const eligible = queue?.cases.filter(c => c.status !== 'cleared' && c.status !== 'monitor') ?? [];
  const exposure = eligible.reduce((s, c) => s + c.dollars_at_risk, 0);
  const clock = [...(queue?.cases ?? [])].filter(c => c.days_until_release != null && c.days_until_release <= 14).sort((a, b) => (a.days_until_release ?? 99) - (b.days_until_release ?? 99));
  const holds = clock.filter(c => c.hold_recommended);

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <div className="eyebrow">Command center · simulation date {o?.sim_today ?? '…'} · synthetic data</div>
          <h1>{f ? <>From {num(f.alerts)} alerts to <span style={{ color: 'var(--accent)' }}>{queue?.selected_count ?? f.selected_today} cases</span> you can act on today.</> : 'Loading…'}</h1>
          <p className="subtitle">Axon explains away what it can, connects what single-claim checks miss, and ranks the rest against your team's hours. Every number traces back to a data field. A human makes every decision.</p>
        </div>
        <div className="page-actions">
          <Button icon={ArrowRight} onClick={() => nav('/queue')}>Open today's queue</Button>
        </div>
      </div>

      <div className="grid-4">
        <Stat icon={Banknote} label="Exposure in open cases" value={queue ? inr(exposure) : '…'} sub={`${eligible.length} cases eligible for review`} />
        <Stat icon={Gauge} label="Expected recovery, today's plan" value={queue ? inr(queue.expected_recovery_selected) : '…'} sub={queue ? `${queue.selected_count} cases · ${queue.hours_used} of ${queue.capacity_hours} hours` : ''} />
        <Stat icon={Clock3} label="Recovery per investigator hour" value={queue ? inr(queue.recovery_per_hour) : '…'} sub="Portfolio-optimized, not sorted by score" />
        <Stat icon={AlarmClock} label="Payment holds to consider" value={queue ? holds.length : '…'} tone={holds.length ? 'warn' : undefined}
          sub={holds.length ? `${inr(holds.reduce((s, c) => s + c.dollars_at_risk, 0))} at risk · human approval needed` : 'Nothing releasing soon'} />
      </div>

      <div className="grid-main">
        <Card title="Exoneration first: alerts explained before a human sees them" icon={Filter}>
          {f ? <Funnel stages={[
            { label: 'Claim lines analysed', value: f.claim_lines },
            { label: 'Raw alerts', value: f.alerts, note: 'Any rule, anomaly, temporal or graph signal' },
            { label: 'Explained by code', value: f.explained, note: 'Cleared with a reason and the facts used' },
            { label: 'Open alerts', value: f.open_alerts },
            { label: 'Cases (grouped)', value: f.cases, note: 'Linked alerts grouped by network' },
            { label: "Today's plan", value: queue?.selected_count ?? f.selected_today, note: `Fits ${queue?.capacity_hours ?? f.capacity_hours} investigator hours` },
          ]} /> : <Skeleton h={220} />}
          <div className="row" style={{ marginTop: 12 }}>
            <Button size="sm" variant="tinted" icon={ArrowRight} onClick={() => nav('/explained')}>See why {f ? num(f.explained) : ''} alerts were cleared</Button>
          </div>
        </Card>

        <Card title="Money clock" icon={Timer} action={<span className="chip">next 14 days</span>}>
          {!queue ? <Skeleton h={200} /> : clock.length === 0 ? <p className="muted small">No pending payments on open cases.</p> : (
            <div className="list" style={{ margin: '-6px -20px -20px' }}>
              {clock.map(c => (
                <div key={c.case_id} className="list-row clickable" onClick={() => nav(`/cases/${c.case_id}`)}>
                  <div style={{ width: 46, textAlign: 'center' }}>
                    <div className="stat-value" style={{ fontSize: '1.4rem', marginTop: 0, color: (c.days_until_release ?? 99) <= 3 ? 'var(--bad-text)' : undefined }}>{c.days_until_release}</div>
                    <div className="xs faint">days</div>
                  </div>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div className="strong small" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.title}</div>
                    <div className="xs muted">{c.case_id} · {inr(c.dollars_at_risk)} · {relDays(c.days_until_release)}</div>
                  </div>
                  {c.hold_recommended ? <span className="chip chip-warn"><AlarmClock size={12} />Hold?</span> : <StrengthPill strength={c.evidence_strength} />}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="grid-main">
        <Card title="Today's plan" icon={UserCheck} action={<Button size="sm" variant="ghost" onClick={() => nav('/queue')}>Full queue</Button>}>
          {!queue ? <Skeleton h={260} /> : (
            <div className="list" style={{ margin: '-6px -20px -20px' }}>
              {queue.cases.filter(c => c.selected).map((c, i) => (
                <motion.div key={c.case_id} className="list-row clickable" onClick={() => nav(`/cases/${c.case_id}`)}
                  initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}>
                  <RiskRing value={c.risk} size={44} />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div className="row-nw" style={{ gap: 8 }}><span className="strong" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.title}</span></div>
                    <div className="xs muted">{c.case_id} · {PATTERN[c.pattern] ?? titleCase(c.pattern)} · {c.effort_hours}h effort{c.exploration ? ' · exploration' : ''}</div>
                  </div>
                  <div style={{ textAlign: 'right' }} className="nowrap">
                    <div className="strong tabular">{inr(c.expected_recovery)}</div>
                    <div className="xs faint">expected</div>
                  </div>
                  <StatusPill status={c.status} />
                </motion.div>
              ))}
            </div>
          )}
        </Card>

        <div className="stack">
          <Card title="Why alerts were cleared" icon={ShieldCheck}>
            {o ? <BarList rows={Object.entries(o.exoneration_by_reason).map(([k, v]) => ({ label: EX_LABEL[k] ?? k, value: v as number }))} /> : <Skeleton h={150} />}
          </Card>
          <Card title="Data loaded" icon={Database} action={o && <span className="chip chip-good">100% synthetic</span>}>
            {o ? <>
              <BarList rows={Object.entries(o.service_types).map(([k, v]) => ({ label: titleCase(k), value: v as number }))} />
              <div className="divider" />
              <div className="row xs muted">
                {Object.entries(o.tables).map(([k, v]) => <span key={k} className="chip">{titleCase(k)} {num(v as number)}</span>)}
              </div>
            </> : <Skeleton h={180} />}
          </Card>
          <Card title="Detection layers" icon={Layers} tight>
            <div className="row">
              {o && Object.entries(o.layers).map(([k, v]) => (
                <span key={k} className={`chip ${v === 'ok' ? 'chip-good' : 'chip-bad'}`}><span className="dot" />{METHOD_LABEL[k] ?? k}: {v === 'ok' ? 'running' : 'unavailable'}</span>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

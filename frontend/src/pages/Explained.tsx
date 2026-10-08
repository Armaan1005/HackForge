import { CheckCircle2, ShieldCheck, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';
import { BarList } from '../components/charts';
import { Banner, Card, ErrorState, Skeleton, SourceBadge } from '../components/ui';
import { ai, api } from '../lib/api';
import { num } from '../lib/format';
import { useAsync } from '../lib/hooks';

const EX_LABEL: Record<string, string> = {
  EX1_sole_provider: 'Sole provider in area', EX2_case_mix_adjusted: 'Case-mix adjusted', EX3_corrected_claim: 'Corrected claim',
  EX4_event_or_seasonal: 'Event or seasonal', EX5_chronic_schedule: 'Chronic schedule', EX6_network_explained: 'Network explained',
};

export function Explained() {
  const cl = useAsync(() => api.cleared(50), []);
  const ov = useAsync(() => api.overview(), []);
  const tr = useAsync(() => api.trust(), []);
  const [lines, setLines] = useState<Record<string, { text: string; source: string }>>({});
  const [aiErr, setAiErr] = useState<string | null>(null);

  useEffect(() => {
    if (!cl.data) return;
    ai.explainCleared(20).then(r => setLines(Object.fromEntries(r.items.map(i => [i.alert_id, { text: i.text, source: i.source }]))))
      .catch(e => setAiErr((e as Error).message));
  }, [cl.data]);

  if (cl.error) return <ErrorState error={cl.error} onRetry={cl.reload} />;
  const wrongly = tr.data?.exoneration.planted_fraud_wrongly_cleared;

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <div className="eyebrow">Exoneration first</div>
          <h1>{cl.data ? num(cl.data.total) : '…'} alerts explained before reaching a human.</h1>
          <p className="subtitle">Before anything enters the queue, code tries to explain it away using peer context: rural sole providers, sicker-than-average patients, corrected claims, region-wide events, chronic treatment schedules. Each clearance keeps the facts it used.</p>
        </div>
      </div>

      <div className="grid-3">
        <Card tight><div className="stat-label"><ShieldCheck size={14} />Hard signals never cleared</div><p className="small muted" style={{ marginTop: 6 }}>Service after death, more than 24 hours a day, ambulance miles over 2× the map distance, and shared identities always reach a human.</p></Card>
        <Card tight><div className="stat-label"><CheckCircle2 size={14} />Planted fraud wrongly cleared</div>
          <div className="stat-value" style={{ color: wrongly === 0 ? 'var(--good-text)' : 'var(--bad-text)' }}>{wrongly ?? '…'}</div><div className="stat-sub">on the synthetic ground truth (Trust panel)</div></Card>
        <Card tight><div className="stat-label"><Sparkles size={14} />One-line explanations</div><p className="small muted" style={{ marginTop: 6 }}>Gemini words each clearance from its facts; numbers are checked against those facts. Clearing itself is always code.</p></Card>
      </div>

      {aiErr && <Banner tone="warn">Explanations unavailable ({aiErr}). The deterministic facts are shown instead.</Banner>}

      <div className="grid-main">
        <Card className="card-flush">
          <div style={{ padding: '14px 16px 4px' }}><h3>Cleared alerts</h3><p className="xs muted">Showing {cl.data?.items.length ?? 0} of {cl.data ? num(cl.data.total) : '…'}</p></div>
          {!cl.data ? <Skeleton h={300} style={{ margin: 16 }} /> : (
            <div className="list">
              {cl.data.items.map(a => (
                <div key={a.alert_id} className="list-row" style={{ alignItems: 'flex-start' }}>
                  <span className="ev-id">{a.alert_id}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="row between"><b>{a.entity_name}</b><span className="chip chip-good"><CheckCircle2 size={12} />{EX_LABEL[a.exoneration_code] ?? a.exoneration_code}</span></div>
                    <div className="small" style={{ marginTop: 4 }}>{lines[a.alert_id]?.text ?? <span className="faint">…</span>}</div>
                    <div className="row xs faint" style={{ marginTop: 6 }}>
                      <span>was risk {a.original_risk}</span>·<span>triggered by {a.triggered_by.join(', ')}</span>
                      {Object.entries(a.facts).map(([kk, v]) => <span key={kk} className="ev-src">{kk}: {Array.isArray(v) ? v.join('–') : String(v)}</span>)}
                      <SourceBadge source={lines[a.alert_id]?.source} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card title="Cleared by reason">
          {ov.data ? <BarList rows={Object.entries(ov.data.exoneration_by_reason).map(([kk, v]) => ({ label: EX_LABEL[kk] ?? kk, value: v as number }))} /> : <Skeleton h={160} />}
          <div className="divider" />
          <p className="xs muted">A clearance requires every incriminating layer to be explained. Partly explained alerts stay open, and their explanation goes to the Defense.</p>
        </Card>
      </div>
    </div>
  );
}

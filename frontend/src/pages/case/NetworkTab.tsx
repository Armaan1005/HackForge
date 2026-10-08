import { Pause, Play, X } from 'lucide-react';
import { Fragment, useEffect, useMemo, useState } from 'react';
import { NetworkGraph } from '../../components/NetworkGraph';
import { Button, Card, ErrorState, Segmented, Skeleton } from '../../components/ui';
import { api } from '../../lib/api';
import { inr, num, pct } from '../../lib/format';
import { useAsync, useInterval } from '../../lib/hooks';
import type { CaseDetail, GNode } from '../../lib/types';

export function NetworkTab({ k, highlight, onClearHighlight }: { k: CaseDetail; highlight: string | null; onClearHighlight: () => void }) {
  const g = useAsync(() => api.graph(k.case_id), [k.case_id]);
  const tm = useAsync(() => api.timemachine(k.case_id), [k.case_id]);
  const [step, setStep] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [sel, setSel] = useState<GNode | null>(null);
  const [proj, setProj] = useState<'30' | '60' | '90'>('30');
  const snaps = tm.data?.snapshots ?? [];
  const idx = step ?? snaps.length - 1;
  useEffect(() => { if (snaps.length && step == null) setStep(snaps.length - 1); }, [snaps.length, step]);
  useInterval(() => { if (playing) setStep(s => { const n = (s ?? 0) + 1; if (n >= snaps.length) { setPlaying(false); return snaps.length - 1; } return n; }); }, 1100);
  const visible = useMemo(() => { const s = snaps[idx]; return s ? new Set([...s.node_ids, ...s.edge_ids]) : undefined; }, [snaps, idx]);

  if (g.error) return <ErrorState error={g.error} onRetry={g.reload} />;
  const ns = k.network_summary;
  const snap = snaps[idx];

  return (
    <div className="grid-main">
      <div className="stack">
        <Card className="card-flush">
          {highlight && <div style={{ padding: '10px 14px 0' }}><span className="chip chip-warn">Highlighting {highlight}<button className="icon-btn" style={{ width: 18, height: 18 }} onClick={onClearHighlight} aria-label="Clear highlight"><X size={12} /></button></span></div>}
          {g.data ? <NetworkGraph nodes={g.data.nodes} edges={g.data.edges} visibleIds={visible} highlightEvidence={highlight} onSelect={setSel} /> : <Skeleton h={560} style={{ borderRadius: 0 }} />}
        </Card>
        {snaps.length > 0 && (
          <Card tight>
            <div className="row-nw" style={{ gap: 14 }}>
              <Button size="sm" variant="tinted" icon={playing ? Pause : Play} onClick={() => { if (!playing && idx >= snaps.length - 1) setStep(0); setPlaying(p => !p); }}>{playing ? 'Pause' : 'Replay'}</Button>
              <input type="range" min={0} max={snaps.length - 1} value={idx} aria-label="Month" style={{ ['--pct' as string]: `${(idx / Math.max(snaps.length - 1, 1)) * 100}%` }}
                onChange={e => { setPlaying(false); setStep(Number(e.target.value)); }} />
              <span className="strong tabular nowrap">{snap?.month}</span>
              <span className="small muted nowrap">risk <b style={{ color: 'var(--text)' }}>{snap?.risk}</b> · {snap?.claims_count} claims · {inr(snap?.amount)}</span>
            </div>
          </Card>
        )}
      </div>

      <div className="stack">
        <Card>
          <div className="grid-2">
            <div className="metric"><div className="k">Connected claims</div><div className="v">{num(ns.connected_claims)}</div></div>
            <div className="metric"><div className="k">Linked & flagged</div><div className="v">{pct(ns.flagged_neighbor_share)}</div></div>
          </div>
        </Card>

        <Card title={sel ? sel.label : 'Details'}>
          {!sel ? <p className="small muted">Tap a node.</p> : (
            <dl className="kv">
              <dt>ID</dt><dd className="mono">{sel.id}</dd>
              <dt>Type</dt><dd>{sel.type.replace(/_/g, ' ')}</dd>
              <dt>Risk</dt><dd>{sel.risk ?? '—'}{sel.flagged ? ' · flagged' : ''}</dd>
              <dt>Since</dt><dd>{sel.first_seen_month}</dd>
              {Object.entries(sel.attrs).map(([a, v]) => <Fragment key={a}><dt>{a.replace(/_/g, ' ')}</dt><dd>{String(v)}</dd></Fragment>)}
            </dl>
          )}
        </Card>

        <Card title="Likely to spread" action={<Segmented size="sm" label="Projection horizon" value={proj} onChange={setProj} options={[{ value: '30', label: '30d' }, { value: '60', label: '60d' }, { value: '90', label: '90d' }]} />}>
          <div className="stack-sm">
            {(tm.data?.projection[proj] ?? []).map(p => (
              <div key={p.entity_id} className="row-nw between small" title={p.label}>
                <span className="mono">{p.entity_id}</span><span className="strong tabular">{pct(p.probability)}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

import { motion } from 'motion/react';
import { Pause, Play, X } from 'lucide-react';
import { Fragment, useEffect, useMemo, useState } from 'react';
import { Spark } from '../../components/charts';
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

  const visible = useMemo(() => {
    const s = snaps[idx];
    return s ? new Set([...s.node_ids, ...s.edge_ids]) : undefined;
  }, [snaps, idx]);

  if (g.error) return <ErrorState error={g.error} onRetry={g.reload} />;
  const ns = k.network_summary;
  const snap = snaps[idx];

  return (
    <div className="grid-main">
      <div className="stack">
        <Card className="card-flush">
          <div className="row between" style={{ padding: '12px 14px' }}>
            <div className="small"><b>Relationship graph</b> <span className="muted">· providers, owners, banks, facilities, locations, members, claims</span></div>
            {highlight && <span className="chip chip-warn">Highlighting {highlight} <button className="icon-btn" style={{ width: 18, height: 18 }} onClick={onClearHighlight} aria-label="Clear highlight"><X size={12} /></button></span>}
          </div>
          {g.data ? <NetworkGraph nodes={g.data.nodes} edges={g.data.edges} visibleIds={visible} highlightEvidence={highlight} onSelect={setSel} /> : <Skeleton h={560} style={{ borderRadius: 0 }} />}
        </Card>

        <Card title="Fraud Time Machine" action={<span className="xs faint">replay how the network formed</span>}>
          {!snaps.length ? <Skeleton h={80} /> : (
            <div className="stack">
              <div className="row-nw" style={{ gap: 12 }}>
                <Button size="sm" variant="tinted" icon={playing ? Pause : Play} onClick={() => { if (!playing && idx >= snaps.length - 1) setStep(0); setPlaying(p => !p); }}>{playing ? 'Pause' : 'Replay'}</Button>
                <input type="range" min={0} max={snaps.length - 1} value={idx} aria-label="Month" style={{ ['--pct' as string]: `${(idx / Math.max(snaps.length - 1, 1)) * 100}%` }}
                  onChange={e => { setPlaying(false); setStep(Number(e.target.value)); }} />
                <span className="strong tabular nowrap">{snap?.month}</span>
              </div>
              <div className="grid-4">
                <div><div className="stat-label">Risk at the time</div><motion.div key={snap?.risk} className="stat-value" initial={{ opacity: 0.4 }} animate={{ opacity: 1 }}>{snap?.risk}</motion.div></div>
                <div><div className="stat-label">Claims that month</div><div className="stat-value">{snap?.claims_count}</div></div>
                <div><div className="stat-label">Billed that month</div><div className="stat-value">{inr(snap?.amount)}</div></div>
                <div><div className="stat-label">Risk trend</div><Spark values={snaps.slice(0, idx + 1).map(s => s.risk)} /></div>
              </div>
            </div>
          )}
        </Card>
      </div>

      <div className="stack">
        <Card title="Network context">
          <div className="grid-2">
            <div><div className="stat-label">Connected claims</div><div className="stat-value">{num(ns.connected_claims)}</div></div>
            <div><div className="stat-label">Community size</div><div className="stat-value">{ns.community_size}</div></div>
            <div><div className="stat-label">Linked providers flagged</div><div className="stat-value">{pct(ns.flagged_neighbor_share)}</div></div>
            <div><div className="stat-label">Graph</div><div className="stat-value" style={{ fontSize: '1.2rem' }}>{ns.node_count} nodes</div><div className="xs faint">{ns.edge_count} edges · {ns.community_id}</div></div>
          </div>
          {g.data?.truncated && <p className="xs faint" style={{ marginTop: 10 }}>Showing up to {g.data.node_cap} nodes; smaller members and claims are grouped.</p>}
        </Card>

        <Card title={sel ? sel.label : 'Select a node'}>
          {!sel ? <p className="small muted">Tap any node to see its details. Red rings mark flagged entities.</p> : (
            <div className="kv">
              <dt>ID</dt><dd className="mono">{sel.id}</dd>
              <dt>Type</dt><dd>{sel.type.replace(/_/g, ' ')}</dd>
              <dt>Risk</dt><dd>{sel.risk ?? '—'}</dd>
              <dt>Flagged</dt><dd>{sel.flagged ? 'Yes' : 'No'}</dd>
              <dt>In case</dt><dd>{sel.in_case ? 'Yes' : 'No (context)'}</dd>
              <dt>First seen</dt><dd>{sel.first_seen_month}</dd>
              {Object.entries(sel.attrs).map(([a, v]) => <Fragment key={a}><dt>{a.replace(/_/g, ' ')}</dt><dd>{String(v)}</dd></Fragment>)}
            </div>
          )}
        </Card>

        <Card title="Projected spread" action={<Segmented size="sm" label="Projection horizon" value={proj} onChange={setProj} options={[{ value: '30', label: '30d' }, { value: '60', label: '60d' }, { value: '90', label: '90d' }]} />}>
          <p className="xs muted" style={{ marginBottom: 8 }}>Likelihood that connected providers show repeat or escalating FWA.</p>
          <div className="stack-sm">
            {(tm.data?.projection[proj] ?? []).map(p => (
              <div key={p.entity_id} className="row-nw between small">
                <span><b className="mono">{p.entity_id}</b>{p.label && <div className="xs muted">{p.label}</div>}</span>
                <span className="strong tabular">{pct(p.probability)}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

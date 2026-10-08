import { Fragment, useEffect, useMemo, useState } from 'react';
import { Icon } from '../../components/Icon';
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
  const month = snap ? new Date(`${snap.month}-01T00:00:00`).toLocaleDateString(undefined, { month: 'short', year: 'numeric' }) : '';

  return (
    <div className="cand-bottom">
      <div className="stack-lg">
        <Card style={{ padding: 0 }}>
          {highlight && <div className="pad row-flex" style={{ paddingBottom: 0 }}><span className="review-pill review-pending">Showing {highlight}</span><Button variant="ghost" size="sm" icon="decline" onClick={onClearHighlight}>Clear</Button></div>}
          {g.data ? <NetworkGraph nodes={g.data.nodes} edges={g.data.edges} visibleIds={visible} highlightEvidence={highlight} onSelect={setSel} /> : <Skeleton h={540} style={{ borderRadius: 0 }} />}
        </Card>
        {snaps.length > 0 && (
          <Card>
            <div className="row-flex" style={{ marginBottom: 10 }}>
              <h2>How it formed</h2><span className="spacer" />
              <span className="small muted">{month} · risk {snap?.risk} · {snap?.claims_count} claims · {inr(snap?.amount)}</span>
            </div>
            <div className="row-nw" style={{ gap: 14 }}>
              <Button size="sm" variant="tinted" icon={playing ? 'pause' : 'play'} onClick={() => { if (!playing && idx >= snaps.length - 1) setStep(0); setPlaying(p => !p); }}>{playing ? 'Pause' : 'Replay'}</Button>
              <input type="range" min={0} max={snaps.length - 1} value={idx} aria-label="Month" style={{ ['--pct' as string]: `${(idx / Math.max(snaps.length - 1, 1)) * 100}%` }}
                onChange={e => { setPlaying(false); setStep(Number(e.target.value)); }} />
            </div>
          </Card>
        )}
      </div>

      <div className="stack-lg">
        <div className="stats" style={{ gridTemplateColumns: '1fr 1fr' }}>
          <div className="stat"><b>{num(ns.connected_claims)}</b><span>connected claims</span></div>
          <div className="stat"><b>{pct(ns.flagged_neighbor_share)}</b><span>of linked providers already flagged</span></div>
        </div>
        <Card>
          <h2 style={{ marginBottom: 12 }}>{sel ? sel.label : 'Tap anything in the network'}</h2>
          {!sel ? <p className="small muted">Providers, owners, bank accounts, facilities, members and claims, and how they connect.</p> : (
            <dl className="facts">
              <div><dt>Type</dt><dd>{sel.type.replace(/_/g, ' ')}</dd></div>
              <div><dt>Risk</dt><dd>{sel.risk ?? '—'}{sel.flagged ? ' · flagged' : ''}</dd></div>
              <div><dt>First seen</dt><dd>{sel.first_seen_month}</dd></div>
              {Object.entries(sel.attrs).map(([a, v]) => <Fragment key={a}><div><dt>{a.replace(/_/g, ' ')}</dt><dd>{String(v)}</dd></div></Fragment>)}
            </dl>
          )}
        </Card>
        <Card>
          <div className="row-flex" style={{ marginBottom: 12 }}><h2>Likely to spread</h2><span className="spacer" />
            <Segmented size="sm" label="Look ahead" value={proj} onChange={setProj} options={[{ value: '30', label: '30d' }, { value: '60', label: '60d' }, { value: '90', label: '90d' }]} /></div>
          <div className="stack">
            {(tm.data?.projection[proj] ?? []).map(p => (
              <div key={p.entity_id} className="row-nw">
                <span className="row-icon"><Icon name="building" size={14} /></span>
                <div style={{ flex: 1, minWidth: 0 }}><b className="small">{p.entity_id}</b>{p.label && <div className="xs muted clamp-1">{p.label}</div>}</div>
                <span className="score-pill">{pct(p.probability)}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

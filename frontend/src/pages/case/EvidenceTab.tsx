import { Network } from 'lucide-react';
import { useState } from 'react';
import { BarList } from '../../components/charts';
import { Card, Segmented } from '../../components/ui';
import { fmtUnit, inr, METHOD_LABEL, num, pct } from '../../lib/format';
import type { CaseDetail, Evidence } from '../../lib/types';

function EvidenceRow({ e, onShowOnGraph }: { e: Evidence; onShowOnGraph: (id: string) => void }) {
  const graphable = e.type === 'graph' || e.entity_ids.length > 1;
  return (
    <div className="evidence" title={`Sources: ${e.sources.map(s => `${s.table}.${s.column}`).join(', ')}`}>
      <span className="ev-id">{e.evidence_id}</span>
      <div style={{ minWidth: 0 }}>
        <div className="row-nw between">
          <span className="strong">{e.name}</span>
          {e.hard && <span className="chip chip-bad">Hard signal</span>}
        </div>
        {e.value != null && e.comparison_value != null ? (
          <div className="small" style={{ marginTop: 3 }}>
            <b>{fmtUnit(e.value, e.unit)}</b> <span className="muted">vs {fmtUnit(e.comparison_value, e.unit)} {e.comparison_label}</span>
          </div>
        ) : <div className="small muted" style={{ marginTop: 3 }}>{e.description}</div>}
        {graphable && <button className="btn btn-ghost btn-sm" style={{ padding: '2px 6px', marginTop: 4, marginLeft: -6 }} onClick={() => onShowOnGraph(e.evidence_id)}><Network size={12} />Show on graph</button>}
      </div>
    </div>
  );
}

export function EvidenceTab({ k, onShowOnGraph }: { k: CaseDetail; onShowOnGraph: (id: string) => void }) {
  const [side, setSide] = useState<'for' | 'against'>('for');
  const list = k.evidence.filter(e => (side === 'for' ? e.direction === 'incriminating' : e.direction !== 'incriminating'));
  const nFor = k.evidence.filter(e => e.direction === 'incriminating').length;
  const cs = k.claims_summary;

  return (
    <div className="grid-main">
      <div className="stack">
        <Card className="card-flush" title="Evidence" action={<Segmented size="sm" label="Evidence side" value={side} onChange={setSide}
          options={[{ value: 'for', label: `Supports review · ${nFor}` }, { value: 'against', label: `Legitimate · ${k.evidence.length - nFor}` }]} />}>
          <div>{list.length ? list.map(e => <EvidenceRow key={e.evidence_id} e={e} onShowOnGraph={onShowOnGraph} />) : <p className="small muted" style={{ padding: 16 }}>None found.</p>}</div>
        </Card>

        <Card className="card-flush" title="Peer comparison">
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Metric</th><th className="num">This case</th><th className="num">Peer median</th><th className="num">Percentile</th><th>Peers</th></tr></thead>
              <tbody>
                {k.peer_context.map(p => {
                  const share = /share/i.test(p.metric) && Math.abs(p.case_value) <= 1;
                  const f = (v: number | null | undefined) => (v == null ? '—' : share ? pct(v) : num(v, 2));
                  return (
                    <tr key={p.evidence_id} title={p.note}>
                      <td>{p.metric}</td>
                      <td className="num strong">{f(p.case_value)}</td>
                      <td className="num">{f(p.peer_median)}</td>
                      <td className="num">{p.percentile ?? '—'}</td>
                      <td className="nowrap small muted">{p.peer_group.label} · {p.peer_group.n}{p.low_sample && <span className="chip chip-warn" style={{ marginLeft: 6 }}>small</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <div className="stack">
        <Card title="One claim looks normal">
          <div className="grid-2">
            <div className="metric"><div className="k">Largest claim</div><div className="v">{inr(cs.amount_max)}</div><div className="s">under {inr(cs.review_threshold)}</div></div>
            <div className="metric"><div className="k">{num(cs.claim_count)} connected</div><div className="v" style={{ color: 'var(--bad-text)' }}>{inr(cs.amount_total)}</div><div className="s">{pct(cs.under_threshold_share)} near the limit</div></div>
          </div>
        </Card>
        <Card title="Signals by method">
          <BarList rows={Object.entries(k.scores.by_method).map(([m, v]) => ({ label: METHOD_LABEL[m] ?? m, value: v }))} format={v => v.toFixed(2)} max={1} />
        </Card>
        {k.missing_documents.length > 0 && (
          <Card title="Missing documents">
            <div className="stack-sm">
              {k.missing_documents.map(m => (
                <div key={m.doc_type} className="row-nw between small" title={m.why}>
                  <span>{titleOf(m.doc_type)} <span className="faint">· {m.claim_count} claims</span></span>
                  {m.critical && <span className="chip chip-warn">critical</span>}
                </div>
              ))}
            </div>
          </Card>
        )}
        <Card tight>
          <details>
            <summary className="row between small strong"><span>Limitations</span><span className="faint">{k.limitations.length}</span></summary>
            <ul className="small muted" style={{ margin: '10px 0 0', paddingLeft: 18 }}>{k.limitations.map(l => <li key={l} style={{ marginBottom: 4 }}>{l}</li>)}</ul>
          </details>
        </Card>
      </div>
    </div>
  );
}

const titleOf = (s: string) => s.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase());

import { AlertTriangle, FileWarning, Network, Scale, Users } from 'lucide-react';
import { Card } from '../../components/ui';
import { fmtUnit, inr, num, pct } from '../../lib/format';
import type { CaseDetail, Evidence } from '../../lib/types';

function EvidenceRow({ e, onShowOnGraph }: { e: Evidence; onShowOnGraph: (id: string) => void }) {
  return (
    <div className="evidence">
      <span className="ev-id">{e.evidence_id}</span>
      <div style={{ minWidth: 0 }}>
        <div className="row-nw between" style={{ alignItems: 'flex-start' }}>
          <span className="strong">{e.name}</span>
          <div className="row" style={{ gap: 6, flexWrap: 'nowrap' }}>
            {e.hard && <span className="chip chip-bad">Hard</span>}
            <span className="chip">{e.method.split('.')[0]}</span>
            <span className="chip" title="Severity 1-5">S{e.severity}</span>
          </div>
        </div>
        <div className="small muted" style={{ marginTop: 3 }}>{e.description}</div>
        {e.value != null && (
          <div className="row small" style={{ marginTop: 6, gap: 14 }}>
            <span>Case <b>{fmtUnit(e.value, e.unit)}</b></span>
            {e.comparison_value != null && <span className="muted">vs <b style={{ color: 'var(--text)' }}>{fmtUnit(e.comparison_value, e.unit)}</b> {e.comparison_label}</span>}
            {e.threshold != null && <span className="faint">threshold {fmtUnit(e.threshold, e.unit)}</span>}
            {e.claim_count > 0 && <span className="faint">{num(e.claim_count)} claims</span>}
          </div>
        )}
        <div className="ev-sources">
          {e.sources.map(s => <span key={s.table + s.column} className="ev-src">{s.table}.{s.column}</span>)}
          {(e.type === 'graph' || e.entity_ids.length > 1) && <button className="btn btn-ghost btn-sm" style={{ padding: '0 6px' }} onClick={() => onShowOnGraph(e.evidence_id)}><Network size={12} />show on graph</button>}
        </div>
      </div>
    </div>
  );
}

export function EvidenceTab({ k, onShowOnGraph }: { k: CaseDetail; onShowOnGraph: (id: string) => void }) {
  const inc = k.evidence.filter(e => e.direction === 'incriminating');
  const exc = k.evidence.filter(e => e.direction !== 'incriminating');
  const cs = k.claims_summary;
  return (
    <div className="grid-main">
      <div className="stack">
        <Card className="card-flush" title={`Evidence supporting review · ${inc.length}`}>
          <div>{inc.map(e => <EvidenceRow key={e.evidence_id} e={e} onShowOnGraph={onShowOnGraph} />)}</div>
        </Card>
        <Card className="card-flush" title={`Evidence suggesting legitimate activity · ${exc.length}`}>
          <div>{exc.length ? exc.map(e => <EvidenceRow key={e.evidence_id} e={e} onShowOnGraph={onShowOnGraph} />) : <p className="small muted" style={{ padding: 16 }}>None found by the engine.</p>}</div>
        </Card>
        <Card className="card-flush">
          <div style={{ padding: '14px 16px 6px' }}><h3>Peer context</h3><p className="xs muted">How this provider compares with its peer group. Agents must quote these numbers.</p></div>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>ID</th><th>Metric</th><th className="num">Case</th><th className="num">Peer median</th><th className="num">Peer p90</th><th className="num">Percentile</th><th>Peer group</th></tr></thead>
              <tbody>
                {k.peer_context.map(p => {
                  const share = /share/i.test(p.metric) && Math.abs(p.case_value) <= 1;
                  const f = (v: number | null | undefined) => (v == null ? '—' : share ? pct(v) : num(v, 2));
                  return (
                    <tr key={p.evidence_id}>
                      <td><span className="ev-id">{p.evidence_id}</span></td>
                      <td><div>{p.metric}</div>{p.note && <div className="xs muted">{p.note}</div>}</td>
                      <td className="num strong">{f(p.case_value)}{p.raw_ratio != null && <div className="xs faint">raw {p.raw_ratio}×</div>}</td>
                      <td className="num">{f(p.peer_median)}</td>
                      <td className="num">{f(p.peer_p90)}</td>
                      <td className="num">{p.percentile == null ? '—' : `${p.percentile}`}</td>
                      <td className="nowrap small">{p.peer_group.label}, n={p.peer_group.n}{p.low_sample && <span className="chip chip-warn" style={{ marginLeft: 6 }}>small sample</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <div className="stack">
        <Card title="One claim looks normal" icon={Users}>
          <p className="small muted">No single claim crosses the {inr(cs.review_threshold)} review threshold, so claim-level screening passes each one.</p>
          <div className="grid-2" style={{ marginTop: 12 }}>
            <div><div className="stat-label">Largest single claim</div><div className="stat-value" style={{ fontSize: '1.4rem' }}>{inr(cs.amount_max)}</div></div>
            <div><div className="stat-label">{num(cs.claim_count)} connected claims</div><div className="stat-value" style={{ fontSize: '1.4rem', color: 'var(--bad-text)' }}>{inr(cs.amount_total)}</div></div>
          </div>
          <div className="small" style={{ marginTop: 10 }}>{pct(cs.under_threshold_share)} of claims sit just under the threshold · range {inr(cs.amount_min)}–{inr(cs.amount_max)}</div>
          <div className="row" style={{ marginTop: 10 }}>{Object.entries(cs.procedure_codes).map(([code, n]) => <span key={code} className="chip">{code} × {n}</span>)}</div>
        </Card>
        <Card title="Missing documents" icon={FileWarning}>
          <div className="stack-sm">
            {k.missing_documents.length === 0 && <span className="small muted">None.</span>}
            {k.missing_documents.map(m => (
              <div key={m.doc_type} className="small">
                <div className="row-nw" style={{ gap: 8 }}><b>{m.doc_type.replace(/_/g, ' ')}</b> <span className="faint">{m.claim_count} claims</span>{m.critical && <span className="chip chip-warn">critical</span>}</div>
                <div className="xs muted">{m.why}</div>
              </div>
            ))}
          </div>
        </Card>
        <Card title="Limitations" icon={AlertTriangle}>
          <ul className="small muted" style={{ margin: 0, paddingLeft: 18 }}>
            {k.limitations.map(l => <li key={l} style={{ marginBottom: 4 }}>{l}</li>)}
          </ul>
        </Card>
        <Card title="Entities" icon={Scale}>
          <div className="stack-sm">
            {k.entities.map(e => (
              <div key={e.entity_id} className="row-nw between small">
                <span><b>{e.name}</b> <span className="xs faint">{e.entity_id}</span></span>
                <span className="chip">{e.role.replace(/_/g, ' ')}{e.risk != null ? ` · ${e.risk}` : ''}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

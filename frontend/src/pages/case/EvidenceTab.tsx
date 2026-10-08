import { useState } from 'react';
import { Icon } from '../../components/Icon';
import { Bar, Button, Card, Segmented } from '../../components/ui';
import { fmtUnit, inr, METHOD_LABEL, num, pct } from '../../lib/format';
import type { CaseDetail, Evidence } from '../../lib/types';

function EvidenceItem({ e, onShowOnGraph }: { e: Evidence; onShowOnGraph: (id: string) => void }) {
  return (
    <details className="ev-item">
      <summary>
        <span className={`row-icon ${e.direction === 'incriminating' ? (e.hard ? 'bad' : 'warn') : ''}`}><Icon name={e.direction === 'incriminating' ? 'inspect' : 'accept'} size={14} /></span>
        <span style={{ flex: 1, minWidth: 0 }}>
          <span style={{ fontWeight: 600 }}>{e.name}</span>
          {e.value != null && e.comparison_value != null && <span className="small muted" style={{ display: 'block' }}>{fmtUnit(e.value, e.unit)} vs {fmtUnit(e.comparison_value, e.unit)} {e.comparison_label}</span>}
        </span>
        <span className="ev-id">{e.evidence_id}</span>
        <Icon name="slim-arrow-right" size={14} className="muted" />
      </summary>
      <div className="stack" style={{ marginTop: 12, paddingLeft: 42 }}>
        <p className="evidence-quote" style={{ marginTop: 0 }}>{e.description}</p>
        <div className="row-flex" style={{ gap: 6 }}>
          {e.sources.map(s => <span key={s.table + s.column} className="src">{s.table}.{s.column}</span>)}
          {(e.type === 'graph' || e.entity_ids.length > 1) && <Button variant="ghost" size="sm" icon="org-chart" onClick={() => onShowOnGraph(e.evidence_id)}>Show on the network</Button>}
        </div>
      </div>
    </details>
  );
}

export function EvidenceTab({ k, onShowOnGraph }: { k: CaseDetail; onShowOnGraph: (id: string) => void }) {
  const [side, setSide] = useState<'for' | 'against'>('for');
  const list = k.evidence.filter(e => (side === 'for' ? e.direction === 'incriminating' : e.direction !== 'incriminating'));
  const nFor = k.evidence.filter(e => e.direction === 'incriminating').length;
  const cs = k.claims_summary;

  return (
    <div className="cand-bottom">
      <div className="stack-lg">
        <Card style={{ padding: 0 }}>
          <div className="pad row-flex"><h2>Evidence</h2><span className="spacer" />
            <Segmented size="sm" label="Evidence side" value={side} onChange={setSide} options={[{ value: 'for', label: `Points to review · ${nFor}` }, { value: 'against', label: `Could be legitimate · ${k.evidence.length - nFor}` }]} />
          </div>
          <div className="group-body" style={{ borderRadius: 0, border: 0, boxShadow: 'none', borderTop: '1px solid var(--line)' }}>
            {list.map(e => <EvidenceItem key={e.evidence_id} e={e} onShowOnGraph={onShowOnGraph} />)}
          </div>
        </Card>

        <Card>
          <h2 style={{ marginBottom: 14 }}>Compared with similar providers</h2>
          <dl className="facts">
            {k.peer_context.map(p => {
              const share = /share/i.test(p.metric) && Math.abs(p.case_value) <= 1;
              const f = (v: number | null | undefined) => (v == null ? '—' : share ? pct(v) : num(v, 2));
              return (
                <div key={p.evidence_id} title={`${p.evidence_id} · ${p.peer_group.label}, ${p.peer_group.n} providers`}>
                  <dt>{p.metric.replace(/\s*\(.*?\)/, '')}</dt>
                  <dd><b>{f(p.case_value)}</b> <span className="muted">vs {f(p.peer_median)} typical</span>{p.percentile != null && <span className="small muted"> · higher than {Math.round(p.percentile)}% of peers</span>}
                    {p.note && <div className="small muted">{p.note}</div>}</dd>
                </div>
              );
            })}
          </dl>
        </Card>
      </div>

      <div className="stack-lg">
        <Card className="card-accent">
          <p className="eyebrow">One claim looks normal</p>
          <h2>{num(cs.claim_count)} connected claims add up to {inr(cs.amount_total)}</h2>
          <p className="small muted" style={{ marginTop: 6 }}>The biggest single claim is {inr(cs.amount_max)}, just under the {inr(cs.review_threshold)} review limit. {pct(cs.under_threshold_share)} of them sit right below it.</p>
        </Card>
        <Card>
          <h2 style={{ marginBottom: 14 }}>How each method sees it</h2>
          <div className="stack">
            {Object.entries(k.scores.by_method).map(([m, v]) => <Bar key={m} label={METHOD_LABEL[m] ?? m} value={v * 100} />)}
          </div>
        </Card>
        <Card>
          <h2 style={{ marginBottom: 12 }}>What Axon can't be sure about</h2>
          <ul className="list-check">{k.limitations.map(l => <li key={l}><Icon name="hint" size={14} /><span className="small">{l}</span></li>)}</ul>
        </Card>
      </div>
    </div>
  );
}

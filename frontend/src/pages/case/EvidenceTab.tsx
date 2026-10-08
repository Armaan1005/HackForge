import { useState } from 'react';
import { Icon } from '../../components/Icon';
import { Bar, Button, Card, Segmented } from '../../components/ui';
import { fmtUnit, inr, METHOD_LABEL, num, pct } from '../../lib/format';
import type { CaseDetail, Evidence } from '../../lib/types';

/** Same finding repeated once per provider (EV-01, -02, -03...) shows as one row. */
function groupEvidence(list: Evidence[]): Evidence[][] {
  const by = new Map<string, Evidence[]>();
  for (const e of list) {
    const key = `${e.name}|${fmtUnit(e.value, e.unit)}|${fmtUnit(e.comparison_value, e.unit)}`;
    by.set(key, [...(by.get(key) ?? []), e]);
  }
  return [...by.values()];
}

function EvidenceItem({ group, onShowOnGraph }: { group: Evidence[]; onShowOnGraph: (id: string) => void }) {
  const e = group[0];
  const descs = [...new Set(group.map(g => g.description))];
  return (
    <details className="ev-item">
      <summary>
        <span className={`row-icon ${e.direction === 'incriminating' ? (e.hard ? 'bad' : 'warn') : ''}`}><Icon name={e.direction === 'incriminating' ? 'inspect' : 'accept'} size={14} /></span>
        <span style={{ flex: 1, minWidth: 0 }}>
          <span style={{ fontWeight: 600 }}>{e.name}</span>
          {e.value != null && e.comparison_value != null && <span className="small muted" style={{ display: 'block' }}>{fmtUnit(e.value, e.unit)} vs {fmtUnit(e.comparison_value, e.unit)} {e.comparison_label}</span>}
        </span>
        {group.length > 1 && <span className="ev-id">×{group.length}</span>}
        <span className="ev-id">{e.evidence_id}{group.length > 1 ? '…' : ''}</span>
        <Icon name="slim-arrow-right" size={14} className="muted" />
      </summary>
      <div className="stack" style={{ marginTop: 12, paddingLeft: 42 }}>
        {descs.map(d => <p key={d} className="evidence-quote" style={{ marginTop: 0 }}>{d}</p>)}
        {group.length > 1 && <p className="xs faint" style={{ margin: 0 }}>{group.map(g => g.evidence_id).join(' · ')}</p>}
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
  const forList = groupEvidence(k.evidence.filter(e => e.direction === 'incriminating'));
  const againstList = groupEvidence(k.evidence.filter(e => e.direction !== 'incriminating'));
  const list = side === 'for' ? forList : againstList;
  const cs = k.claims_summary;

  return (
    <div className="cand-bottom">
      <div className="stack-lg">
        <Card style={{ padding: 0 }}>
          <div className="pad row-flex"><h2>Evidence</h2><span className="spacer" />
            <Segmented size="sm" label="Evidence side" value={side} onChange={setSide} options={[{ value: 'for', label: `Points to review · ${forList.length}` }, { value: 'against', label: `Could be legitimate · ${againstList.length}` }]} />
          </div>
          <div className="group-body" style={{ borderRadius: 0, border: 0, boxShadow: 'none', borderTop: '1px solid var(--line)' }}>
            {list.map(g => <EvidenceItem key={g[0].evidence_id} group={g} onShowOnGraph={onShowOnGraph} />)}
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
        <Card className="side-panel">
          <section>
          <p className="eyebrow">One claim looks normal</p>
          <h2>{num(cs.claim_count)} connected claims add up to {inr(cs.amount_total)}</h2>
          <p className="small muted" style={{ marginTop: 6 }}>The biggest single claim is {inr(cs.amount_max)}, just under the {inr(cs.review_threshold)} review limit. {pct(cs.under_threshold_share)} of them sit right below it.</p>
          </section>
          <section>
          <h3>How each method sees it</h3>
          <div className="stack">
            {Object.entries(k.scores.by_method).map(([m, v]) => <Bar key={m} label={METHOD_LABEL[m] ?? m} value={v * 100} />)}
          </div>
          </section>
          <section>
          <h3>What Axon can't be sure about</h3>
          <ul className="list-check">{k.limitations.map(l => <li key={l}><Icon name="hint" size={14} /><span className="small">{l}</span></li>)}</ul>
          </section>
        </Card>
      </div>
    </div>
  );
}

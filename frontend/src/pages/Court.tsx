import { useNavigate, useSearchParams } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { Mascot } from '../components/Mascot';
import { Button, Chip, ErrorState, PageHeader, RiskPill, Skeleton, Status } from '../components/ui';
import { api } from '../lib/api';
import { inr, PATTERN, PATTERN_ICON } from '../lib/format';
import { useAsync } from '../lib/hooks';
import { CourtRoom } from './case/CourtTab';

/** Evidence Court: pick a case and watch Prosecution and Defense argue it before you rule. */
export function CourtPage() {
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const q = useAsync(() => api.queue(40, 30), []);
  const docket = q.data?.cases.filter(c => c.status !== 'cleared') ?? [];
  const caseId = params.get('case') ?? docket[0]?.case_id ?? null;
  const k = useAsync(() => (caseId ? api.case(caseId) : Promise.resolve(null)), [caseId]);
  const row = docket.find(c => c.case_id === caseId);

  return (
    <>
      <PageHeader eyebrow="Evidence Court" title="Every case gets a fair hearing"
       
        actions={<Mascot size={84} mood="watching" />} />

      <div className="row-flex" style={{ marginBottom: 18 }}>
        <span className="small strong">On the docket</span>
        {!q.data ? <Skeleton h={34} style={{ width: 300 }} /> : docket.map(c => (
          <Chip key={c.case_id} selected={c.case_id === caseId} onClick={() => setParams({ case: c.case_id })}>{c.case_id.replace('CASE-', '#')} · {PATTERN[c.pattern] ?? c.pattern}</Chip>
        ))}
      </div>

      {row && (
        <div className="case-bar">
          <div className="row-flex">
            <span className="row-icon"><Icon name={PATTERN_ICON[row.pattern] ?? 'inspect'} size={15} /></span>
            <b style={{ flex: 1, minWidth: 200 }}>{row.title}</b>
            <span className="small muted">{inr(row.dollars_at_risk)} at stake</span>
            <RiskPill value={row.risk} />
            <Status value={row.status} />
            <Button size="sm" variant="ghost" iconRight="slim-arrow-right" onClick={() => nav(`/cases/${row.case_id}`)}>Full case</Button>
          </div>
        </div>
      )}

      {k.error ? <ErrorState error={k.error} onRetry={k.reload} /> : !k.data ? <Skeleton h={360} /> : <CourtRoom key={k.data.case_id} k={k.data} decide />}
    </>
  );
}

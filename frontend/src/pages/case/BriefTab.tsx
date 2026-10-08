import { Download, FileText, Printer } from 'lucide-react';
import { Markdown } from '../../components/Markdown';
import { Banner, Button, Card, ErrorState, Skeleton, SourceBadge } from '../../components/ui';
import { ai, briefDownloadUrl } from '../../lib/api';
import { useAsync } from '../../lib/hooks';
import type { CaseDetail } from '../../lib/types';

export function BriefTab({ k }: { k: CaseDetail }) {
  const b = useAsync(() => ai.brief(k.case_id), [k.case_id]);
  if (b.error) return <ErrorState error={new Error(`The brief needs the Part B backend on :8000 (${b.error.message}).`)} onRetry={b.reload} />;
  if (!b.data) return <div className="stack"><Banner icon={FileText}>Drafting the investigation brief from verified evidence…</Banner><Skeleton h={500} /></div>;
  return (
    <Card title="Investigation brief" icon={FileText}
      action={<div className="row no-print">
        <SourceBadge source={b.data.source} />
        <a className="btn btn-secondary btn-sm" href={briefDownloadUrl(k.case_id)} download><Download size={14} />Markdown</a>
        <Button size="sm" variant="secondary" icon={Printer} onClick={() => window.print()}>Print / PDF</Button>
      </div>}>
      <Markdown text={b.data.markdown} />
    </Card>
  );
}

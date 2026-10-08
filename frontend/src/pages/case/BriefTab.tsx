import { Icon } from '../../components/Icon';
import { Markdown } from '../../components/Markdown';
import { Button, Card, ErrorState, Skeleton } from '../../components/ui';
import { ai, briefDownloadUrl } from '../../lib/api';
import { useAsync } from '../../lib/hooks';
import type { CaseDetail } from '../../lib/types';

export function BriefTab({ k }: { k: CaseDetail }) {
  const b = useAsync(() => ai.brief(k.case_id), [k.case_id]);
  if (b.error) return <ErrorState error={new Error(`Couldn't reach the AI service (${b.error.message}).`)} onRetry={b.reload} />;
  if (!b.data) return <Skeleton h={500} />;
  return (
    <Card style={{ maxWidth: 900 }}>
      <div className="row-flex no-print" style={{ marginBottom: 6 }}>
        <span className="engine-pill"><Icon name="document-text" size={13} />Investigation brief</span>
        <span className="spacer" />
        <a className="btn btn-secondary btn-sm" href={briefDownloadUrl(k.case_id)} download><Icon name="download" size={14} />Download</a>
        <Button size="sm" variant="secondary" icon="print" onClick={() => window.print()}>Print</Button>
      </div>
      <Markdown text={b.data.markdown} />
    </Card>
  );
}

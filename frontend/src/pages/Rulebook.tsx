import { forwardRef, useMemo, useRef, useState, type ReactNode } from 'react';
import HTMLFlipBook from 'react-pageflip';
import { useSearchParams } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { MascotMark } from '../components/Mascot';
import { Button, ErrorState, PageHeader, Section, Skeleton } from '../components/ui';
import { ai, api } from '../lib/api';
import { useAsync } from '../lib/hooks';
import type { RulebookEntry } from '../lib/types';

// Fixed front matter: cover, how-to page, two contents pages. Rule pages follow; back cover last.
const FRONT = 4;
const TOC_SPLIT = 22;

const Page = forwardRef<HTMLDivElement, { children: ReactNode; hard?: boolean; side?: 'left' | 'right'; className?: string }>(
  ({ children, hard, side, className = '' }, ref) => (
    <div ref={ref} className={`bk-page ${hard ? 'hard' : ''} ${side ?? ''} ${className}`} data-density={hard ? 'hard' : 'soft'}>
      <div className="bk-inner">{children}</div>
    </div>
  ));
Page.displayName = 'Page';

interface FlipApi { pageFlip(): { flip(n: number): void; flipNext(): void; flipPrev(): void; getPageCount(): number } | undefined }

export function Rulebook() {
  const [params, setParams] = useSearchParams();
  const caseId = params.get('case') ?? '';
  const book = useAsync(() => ai.rulebook(), []);
  const hits = useAsync(() => (caseId ? ai.rulebook(caseId) : Promise.resolve(null)), [caseId]);
  const queue = useAsync(() => api.queue(40, 30), []);
  const ref = useRef<FlipApi>(null);
  const [page, setPage] = useState(0);
  const [query, setQuery] = useState('');

  const entries = book.data?.entries ?? [];
  const pageOf = (id: string) => FRONT + entries.findIndex(e => e.id === id);
  const retrieved = useMemo(() => new Map((hits.data?.retrieved ?? []).map((r, i) => [r.id, { score: r.score, rank: i + 1 }])), [hits.data]);
  const startRule = params.get('rule');
  const start = useMemo(() => (startRule && entries.some(e => e.id === startRule) ? pageOf(startRule) : 0), [entries.length]); // eslint-disable-line react-hooks/exhaustive-deps
  const flip = (n: number) => ref.current?.pageFlip()?.flip(n);
  const found = query.trim().length > 1 ? entries.filter(e => `${e.id} ${e.title} ${e.tags}`.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 6) : [];

  if (book.error) return <ErrorState error={new Error(`Couldn't load the rulebook (${book.error.message}).`)} onRetry={book.reload} />;
  if (!book.data) return <Skeleton h={600} />;
  const total = FRONT + entries.length + 1;
  const pol = entries.filter(e => e.kind === 'payer_rule').length, law = entries.length - pol;
  const side = (i: number): 'left' | 'right' => (i % 2 ? 'left' : 'right');

  const tocLine = (e: RulebookEntry) => {
    const hit = retrieved.get(e.id);
    return (
      <button key={e.id} type="button" className={`bk-toc-line ${hit ? 'hit' : ''}`} onClick={() => flip(pageOf(e.id))}>
        <span className="bk-toc-id">{e.id}</span><span className="bk-toc-title">{e.title}</span><span className="bk-toc-dots" /><span>{pageOf(e.id) + 1}</span>
      </button>
    );
  };

  return (
    <>
      <PageHeader eyebrow="Rulebook" title="The book Axon reads from"
        subtitle={`${pol} payer rules and ${law} law summaries. Agents may cite only the pages pulled for their case.`} />

      <div className="bk-layout">
        <div className="bk-stage">
          <HTMLFlipBook ref={ref} className="bk" style={{}} startPage={start} size="stretch" width={420} height={560} minWidth={260} maxWidth={460}
            minHeight={360} maxHeight={613} drawShadow flippingTime={700} usePortrait startZIndex={0} autoSize maxShadowOpacity={0.35} showCover
            mobileScrollSupport clickEventForward useMouseEvents swipeDistance={30} showPageCorners disableFlipByClick
            onFlip={(e: { data: number }) => setPage(e.data)} onInit={(e: { data: { page: number } }) => setPage(e.data.page)}>
            <Page hard className="bk-cover">
              <MascotMark size={72} />
              <h2>Axon Rulebook</h2>
              <p>Payer rules and law summaries for SIU review</p>
              <span className="bk-cover-foot">Synthetic payer rules · paraphrased Indian law</span>
            </Page>

            <Page side={side(1)}>
              <h3 className="bk-h">How this book is used</h3>
              <ol className="bk-list">
                <li><b>Search.</b> For each case, Axon runs a keyword search (BM25) over these pages using the case’s pattern and evidence.</li>
                <li><b>Cite.</b> The prosecution, defense, clerk, brief and ask agents see only the pages found, and may cite them next to case evidence, never alone.</li>
                <li><b>Check.</b> The Citation Verifier strikes any rule that wasn’t retrieved, and never takes a number from a rule as a case fact.</li>
                <li><b>Decide.</b> Rules add context. They never change a score, and a person makes every call.</li>
              </ol>
              <div className="bk-note"><Icon name="official-service" size={14} /><span><b>LAW pages</b> are short paraphrases of public Indian laws and rules, not quotes or legal advice. Check the official text before relying on one.</span></div>
              <span className="bk-num">2</span>
            </Page>

            <Page side={side(2)}>
              <h3 className="bk-h">Contents</h3>
              <div className="bk-toc">{entries.slice(0, TOC_SPLIT).map(tocLine)}</div>
              <span className="bk-num">3</span>
            </Page>
            <Page side={side(3)}>
              <h3 className="bk-h">Contents, continued</h3>
              <div className="bk-toc">{entries.slice(TOC_SPLIT).map(tocLine)}</div>
              <span className="bk-num">4</span>
            </Page>

            {entries.map((e, n) => {
              const i = FRONT + n, hit = retrieved.get(e.id);
              return (
                <Page key={e.id} side={side(i)} className={e.kind === 'law' ? 'law' : ''}>
                  {hit && <span className="bk-ribbon" title={`Retrieved for ${caseId}, rank ${hit.rank}`}>Pulled for {caseId}</span>}
                  <div className="bk-kicker"><span className="bk-id">{e.id}</span>{e.kind === 'law' ? 'Law summary' : 'Payer rule · synthetic'}</div>
                  <h3 className="bk-title">{e.title}</h3>
                  {!(e.kind === 'law' && e.detail?.length) && <p className="bk-text bk-lead">{e.text.replace(/^Summary: (.)/, (_, c: string) => c.toUpperCase())}</p>}
                  {e.kind === 'law'
                    ? e.detail?.map(d => <p key={d.slice(0, 20)} className="bk-text">{d}</p>)
                    : e.detail?.map(d => <p key={d.slice(0, 20)} className="bk-text"><span className="bk-label">In practice</span>{d}</p>)}
                  {e.kind === 'law' && <div className="bk-note warn"><Icon name="alert" size={14} /><span>Paraphrase, not legal advice. Check the official text.</span></div>}
                  <div className="bk-meta"><span className="bk-label">Source</span>{e.source}</div>
                  {hit && <div className="bk-meta"><span className="bk-label">Match for {caseId}</span>rank {hit.rank} of {retrieved.size} · BM25 score {hit.score}</div>}
                  <span className="bk-num">{i + 1}</span>
                </Page>
              );
            })}

            <Page hard className="bk-cover back">
              <MascotMark size={44} />
              <p>Rules give context. A person decides.</p>
            </Page>
          </HTMLFlipBook>

          <div className="bk-controls">
            <Button size="sm" variant="secondary" icon="slim-arrow-left" onClick={() => ref.current?.pageFlip()?.flipPrev()} disabled={page === 0}>Back</Button>
            <span className="small muted">Page {page + 1} of {total}</span>
            <Button size="sm" variant="secondary" iconRight="slim-arrow-right" onClick={() => ref.current?.pageFlip()?.flipNext()} disabled={page >= total - 1}>Next</Button>
          </div>
          <p className="xs faint" style={{ textAlign: 'center' }}>Drag a page corner, swipe, or use the arrows.</p>
        </div>

        <div className="stack-lg">
          <div className="card" style={{ padding: 16 }}>
            <label className="small" htmlFor="bk-case" style={{ fontWeight: 600 }}>Show what Axon pulls for a case</label>
            <select id="bk-case" className="bk-select" value={caseId} onChange={e => setParams(e.target.value ? { case: e.target.value } : {})}>
              <option value="">No case selected</option>
              {queue.data?.cases.map(c => <option key={c.case_id} value={c.case_id}>{c.case_id} · {c.title}</option>)}
            </select>
            <label className="small" htmlFor="bk-find" style={{ fontWeight: 600, marginTop: 14, display: 'block' }}>Find a rule</label>
            <input id="bk-find" className="bk-select" placeholder="e.g. duplicate, forgery, POL-014" value={query} onChange={e => setQuery(e.target.value)} />
            {found.map(e => (
              <button key={e.id} type="button" className="bk-find-hit" onClick={() => flip(pageOf(e.id))}><b>{e.id}</b> {e.title}</button>
            ))}
          </div>

          {caseId && (hits.data ? (
            <Section title={`Pages pulled for ${caseId}`} footer="Ranked by keyword match. Agents may cite only these pages for this case.">
              {hits.data.retrieved.map((r, n) => {
                const e = entries.find(x => x.id === r.id);
                return (
                  <div key={r.id} className="row clickable" role="button" tabIndex={0} onClick={() => flip(pageOf(r.id))} onKeyDown={k => k.key === 'Enter' && flip(pageOf(r.id))}>
                    <span className={`row-icon ${e?.kind === 'law' ? 'warn' : ''}`}><Icon name={e?.kind === 'law' ? 'official-service' : 'course-book'} size={15} /></span>
                    <div className="row-text"><span className="row-label">{e?.title ?? r.id}</span><span className="row-desc">{r.id} · rank {n + 1} · p. {pageOf(r.id) + 1}</span></div>
                    <Icon name="slim-arrow-right" size={14} className="muted" />
                  </div>
                );
              })}
            </Section>
          ) : <Skeleton h={300} />)}
        </div>
      </div>
    </>
  );
}

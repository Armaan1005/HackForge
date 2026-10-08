import { motion } from 'motion/react';
import { ArrowRight, FlaskConical, QrCode, Sparkles, Wand2, Wrench } from 'lucide-react';
import QRCode from 'qrcode';
import { useEffect, useState } from 'react';
import { BarList } from '../components/charts';
import { NetworkGraph } from '../components/NetworkGraph';
import { Banner, Button, Card, Skeleton, SourceBadge } from '../components/ui';
import { ai, api } from '../lib/api';
import { METHOD_LABEL, num, pct } from '../lib/format';
import { useAsync } from '../lib/hooks';
import type { TwinRun, TwinScenarioSpec } from '../lib/types';

type Parsed = { scenario: string; scenario_name?: string; params: Record<string, unknown>; adjustments?: string[]; source: string };

export function Twin() {
  const wl = useAsync(() => api.twinScenarios(), []);
  const [text, setText] = useState('What if fraudsters split ₹2 lakh claims into four ₹50,000 claims?');
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [parseMsg, setParseMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState<'parse' | 'run' | 'advise' | 'harden' | null>(null);
  const [run, setRun] = useState<TwinRun | null>(null);
  const [advice, setAdvice] = useState<Awaited<ReturnType<typeof ai.twinAdvise>> | null>(null);
  const [hardened, setHardened] = useState<TwinRun | null>(null);
  const scenarios = (wl.data?.scenarios ?? []) as unknown as TwinScenarioSpec[];
  const spec = scenarios.find(s => s.id === parsed?.scenario);

  const doParse = async () => {
    setBusy('parse'); setParseMsg(null); setRun(null); setAdvice(null); setHardened(null);
    try {
      const r = await ai.twinParse(text);
      if (r.supported && r.scenario) setParsed({ scenario: r.scenario, scenario_name: r.scenario_name, params: r.params ?? {}, adjustments: r.adjustments, source: r.source });
      else { setParsed(null); setParseMsg(r.reason ?? 'Not a supported scenario.'); }
    } catch (e) { setParseMsg(`Scenario Parser needs the Part B backend (${(e as Error).message}). Pick a scenario manually below.`); }
    finally { setBusy(null); }
  };
  const pick = (s: TwinScenarioSpec) => { setParsed({ scenario: s.id, scenario_name: s.name, params: Object.fromEntries(Object.entries(s.params).map(([k, v]) => [k, v.default])), source: 'manual' }); setParseMsg(null); setRun(null); setAdvice(null); setHardened(null); };
  const doRun = async () => {
    if (!parsed) return;
    setBusy('run'); setAdvice(null); setHardened(null);
    try {
      const r = await api.twinRun(parsed.scenario, parsed.params);
      setRun(r);
      if (r.missed > 0) { setBusy('advise'); ai.twinAdvise(r).then(setAdvice).catch(() => setAdvice(null)).finally(() => setBusy(null)); return; }
    } finally { setBusy(b => (b === 'run' ? null : b)); }
  };
  const doHarden = async () => {
    if (!run || !advice?.suggested_change) return;
    setBusy('harden');
    try { setHardened(await api.twinHarden(run.run_id, advice.suggested_change.param, advice.suggested_change.new_value)); } finally { setBusy(null); }
  };

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <div className="eyebrow">Fraud Twin · detection stress test</div>
          <h1>Can our detection survive tomorrow's fraud?</h1>
          <p className="subtitle">Describe how a fraudster might adapt. Axon turns it into a whitelisted synthetic attack, injects it into a sandbox copy of the data, reruns every detector, and reports what was caught, what was missed, and why.</p>
        </div>
      </div>

      <div className="grid-main">
        <Card title="What if…" icon={Wand2}>
          <div className="stack">
            <textarea className="textarea" value={text} onChange={e => setText(e.target.value)} maxLength={600} aria-label="Describe a fraud scheme" />
            <div className="row">
              {scenarios.flatMap(s => s.examples.slice(0, 1)).map(ex => <button key={ex} className="chip chip-outline" style={{ cursor: 'pointer', border: 0 }} onClick={() => setText(ex)}>{ex}</button>)}
            </div>
            <div className="row">
              <Button icon={Sparkles} loading={busy === 'parse'} onClick={doParse}>Build attack</Button>
              <span className="xs faint">or pick:</span>
              {scenarios.map(s => <Button key={s.id} size="sm" variant={parsed?.scenario === s.id ? 'tinted' : 'ghost'} onClick={() => pick(s)}>{s.name}</Button>)}
            </div>
            {parseMsg && <Banner tone="warn">{parseMsg}</Banner>}
            {parsed && spec && (
              <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="card" style={{ background: 'var(--surface-2)', boxShadow: 'none' }}>
                <div className="row between"><b>{spec.name}</b><SourceBadge source={parsed.source === 'manual' ? undefined : parsed.source} /></div>
                <p className="xs muted" style={{ margin: '4px 0 10px' }}>{spec.description}</p>
                <div className="grid-3">
                  {Object.entries(spec.params).map(([k, p]) => (
                    <label key={k} className="stack-sm">
                      <span className="xs muted">{k.replace(/_/g, ' ')}{p.min != null ? ` (${p.min}–${p.max})` : ''}</span>
                      {p.type === 'bool' ? (
                        <select className="input" value={String(parsed.params[k])} onChange={e => setParsed({ ...parsed, params: { ...parsed.params, [k]: e.target.value === 'true' } })}><option value="true">yes</option><option value="false">no</option></select>
                      ) : p.type === 'enum' ? (
                        <select className="input" value={String(parsed.params[k])} onChange={e => setParsed({ ...parsed, params: { ...parsed.params, [k]: e.target.value } })}>{p.values?.map(v => <option key={v}>{v}</option>)}</select>
                      ) : (
                        <input className="input" type="number" min={p.min} max={p.max} step={p.type === 'float' ? 0.05 : 1} value={Number(parsed.params[k])}
                          onChange={e => setParsed({ ...parsed, params: { ...parsed.params, [k]: Math.min(Math.max(Number(e.target.value), p.min ?? -Infinity), p.max ?? Infinity) } })} />
                      )}
                    </label>
                  ))}
                </div>
                {!!parsed.adjustments?.length && <p className="xs faint" style={{ marginTop: 8 }}>Adjusted: {parsed.adjustments.join('; ')}</p>}
                <div className="row" style={{ marginTop: 12 }}><Button icon={FlaskConical} loading={busy === 'run'} onClick={doRun}>Run stress test</Button><span className="xs faint">sandbox only · never touches the live queue</span></div>
              </motion.div>
            )}
          </div>
        </Card>
        <JudgeQr />
      </div>

      {run && <Results run={run} />}

      {run && run.missed > 0 && (
        <Card title="Hardening advisor" icon={Wrench}>
          {busy === 'advise' ? <Skeleton h={80} /> : !advice?.suggested_change ? <p className="small muted">{advice?.explanation ?? 'No tunable parameter explains these misses.'}</p> : (
            <div className="stack">
              <div className="row"><SourceBadge source={advice.source} /><span className="strong mono">{advice.suggested_change.param}</span><span className="chip">{advice.suggested_change.old_value}</span><ArrowRight size={14} /><span className="chip chip-accent">{advice.suggested_change.new_value}</span></div>
              <p className="small">{advice.explanation}</p>
              <div className="row">
                <Button icon={Wrench} loading={busy === 'harden'} onClick={doHarden} disabled={!!hardened}>Approve and rerun in sandbox</Button>
                <span className="xs faint">The analyst decides. Applying it to live detection is a separate human decision.</span>
              </div>
              {hardened && <Compare before={run} after={hardened} />}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

function Results({ run }: { run: TwinRun }) {
  const g = run.injected_graph;
  return (
    <div className="stack">
      <div className="grid-4">
        <Card tight><div className="stat-label">Detection rate</div><div className="stat-value" style={{ fontSize: '2.4rem' }}>{pct(run.detection_rate, 1)}</div><div className="stat-sub">{num(run.detected)} of {num(run.generated)} injected claims</div></Card>
        <Card tight><div className="stat-label">Missed</div><div className="stat-value" style={{ color: run.missed ? 'var(--warn-text)' : 'var(--good-text)' }}>{num(run.missed)}</div><div className="stat-sub">reasons below</div></Card>
        <Card tight><div className="stat-label">False-positive rate</div><div className="stat-value">{pct(run.false_positive_rate.run, 1)}</div><div className="stat-sub">baseline {pct(run.false_positive_rate.baseline, 1)} on clean claims</div></Card>
        <Card tight><div className="stat-label">Run</div><div className="stat-value" style={{ fontSize: '1.1rem' }}>{run.run_id}</div><div className="stat-sub">seed {run.seed} · {(run.runtime_ms / 1000).toFixed(1)}s · sandbox</div></Card>
      </div>
      <div className="grid-main">
        <Card title="Which detector caught it">
          <BarList rows={Object.entries(run.by_layer).map(([k, v]) => ({ label: METHOD_LABEL[k] ?? k, value: v, hint: `${pct(v / run.generated)} of injected claims` }))} max={run.generated} />
          <p className="xs muted" style={{ marginTop: 8 }}>Layers overlap. A claim counts as detected if any layer flags it into an open case. Rules alone would have caught {pct((run.by_layer.rules ?? 0) / run.generated)}.</p>
          <div className="divider" />
          <h3 style={{ marginBottom: 8 }}>Why claims were missed</h3>
          {run.miss_reason_summary.map(m => (
            <div key={m.reason_code} className="row-nw between small" style={{ padding: '4px 0' }}>
              <span><b>{m.count}</b> · {m.reason_code.replace(/_/g, ' ').toLowerCase()} <span className="mono xs faint">{m.param_key}</span></span>
              <span className="muted nowrap">threshold {m.threshold} · typical {m.typical_value}</span>
            </div>
          ))}
          {run.missed_claims.slice(0, 3).map(m => <div key={m.claim_id} className="xs muted">• <span className="mono">{m.claim_id}</span>: {m.description}</div>)}
        </Card>
        <Card title="Injected network" className="card-flush">
          {g.nodes.length ? <NetworkGraph nodes={g.nodes} edges={g.edges} injectedIds={new Set(g.nodes.map(n => n.id))} /> : <p className="small muted" style={{ padding: 16 }}>No graph for this run.</p>}
        </Card>
      </div>
      {run.limitations.map(l => <Banner key={l} tone="warn">{l}</Banner>)}
    </div>
  );
}

function Compare({ before, after }: { before: TwinRun; after: TwinRun }) {
  const b = after.before ?? { detection_rate: before.detection_rate, false_positive_rate: before.false_positive_rate.run };
  const a = after.after ?? { detection_rate: after.detection_rate, false_positive_rate: after.false_positive_rate.run };
  const fpDelta = (a.false_positive_rate - b.false_positive_rate) * 100;
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="grid-2">
      <Card tight><div className="stat-label">Detection rate</div><div className="row" style={{ alignItems: 'baseline' }}><span className="faint">{pct(b.detection_rate, 1)}</span><ArrowRight size={14} /><span className="stat-value" style={{ color: 'var(--good-text)' }}>{pct(a.detection_rate, 1)}</span></div></Card>
      <Card tight><div className="stat-label">False-positive rate</div><div className="row" style={{ alignItems: 'baseline' }}><span className="faint">{pct(b.false_positive_rate, 1)}</span><ArrowRight size={14} /><span className="stat-value">{pct(a.false_positive_rate, 1)}</span></div>
        <div className="stat-sub">{fpDelta <= 0.5 ? `+${fpDelta.toFixed(1)} pp: acceptable` : `+${fpDelta.toFixed(1)} pp: review before applying`}</div></Card>
    </motion.div>
  );
}

function JudgeQr() {
  const [url, setUrl] = useState(() => `${window.location.origin}/challenge`);
  const [svg, setSvg] = useState('');
  useEffect(() => { QRCode.toString(url, { type: 'svg', margin: 1, width: 180 }).then(setSvg).catch(() => setSvg('')); }, [url]);
  const local = /localhost|127\.0\.0\.1/.test(url);
  return (
    <Card title="Judge challenge" icon={QrCode}>
      <p className="small muted">Judges scan, type a scheme on their phone, and watch Axon try to catch it live.</p>
      <div style={{ display: 'grid', placeItems: 'center', margin: '14px 0', background: '#fff', borderRadius: 14, padding: 10 }} dangerouslySetInnerHTML={{ __html: svg }} />
      <input className="input mono xs" value={url} onChange={e => setUrl(e.target.value)} aria-label="Challenge URL" />
      {local && <p className="xs faint" style={{ marginTop: 6 }}>Phones can't open localhost. Replace it with this laptop's Wi-Fi IP (the dev server listens on the LAN) or a tunnel URL.</p>}
    </Card>
  );
}

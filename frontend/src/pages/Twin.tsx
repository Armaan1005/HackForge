import { motion } from 'motion/react';
import QRCode from 'qrcode';
import { useEffect, useState } from 'react';
import { Icon } from '../components/Icon';
import { Mascot, type MascotMood } from '../components/Mascot';
import { TwinFlow } from '../components/TwinFlow';
import { NetworkGraph } from '../components/NetworkGraph';
import { Bar, Button, Card, Chip, Note, PageHeader, Ring, Skeleton } from '../components/ui';
import { ai, api } from '../lib/api';
import { METHOD_LABEL, num, pct } from '../lib/format';
import { useAsync } from '../lib/hooks';
import { spring } from '../lib/theme';
import type { TwinRun, TwinScenarioSpec } from '../lib/types';

type Parsed = { scenario: string; params: Record<string, unknown>; adjustments?: string[] };

export function Twin() {
  const wl = useAsync(() => api.twinScenarios(), []);
  const [text, setText] = useState('What if fraudsters split ₹2 lakh claims into four ₹50,000 claims?');
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState<'parse' | 'run' | 'advise' | 'harden' | null>(null);
  const [run, setRun] = useState<TwinRun | null>(null);
  const [advice, setAdvice] = useState<Awaited<ReturnType<typeof ai.twinAdvise>> | null>(null);
  const [hardened, setHardened] = useState<TwinRun | null>(null);
  const scenarios = (wl.data?.scenarios ?? []) as unknown as TwinScenarioSpec[];
  const spec = scenarios.find(s => s.id === parsed?.scenario);
  const [howOpen, setHowOpen] = useState(true);
  const mood: MascotMood = busy ? 'thinking' : hardened ? 'happy' : run ? 'watching' : 'watching';

  const reset = () => { setRun(null); setAdvice(null); setHardened(null); };
  const build = async () => {
    setBusy('parse'); setMsg(null); reset();
    try {
      const r = await ai.twinParse(text);
      if (r.supported && r.scenario) setParsed({ scenario: r.scenario, params: r.params ?? {}, adjustments: r.adjustments });
      else { setParsed(null); setMsg(r.reason ?? "I can't simulate that one yet."); }
    } catch (e) { setMsg(`Couldn't reach the AI service (${(e as Error).message}). Pick a scheme below instead.`); }
    finally { setBusy(null); }
  };
  const go = async () => {
    if (!parsed) return;
    setBusy('run'); reset();
    const r = await api.twinRun(parsed.scenario, parsed.params);
    setRun(r);
    if (r.missed > 0) { setBusy('advise'); ai.twinAdvise(r).then(setAdvice).catch(() => setAdvice(null)).finally(() => setBusy(null)); }
    else setBusy(null);
  };
  const harden = async () => {
    if (!run || !advice?.suggested_change) return;
    setBusy('harden');
    try { setHardened(await api.twinHarden(run.run_id, advice.suggested_change.param, advice.suggested_change.new_value)); } finally { setBusy(null); }
  };

  return (
    <>
      <PageHeader eyebrow="Fraud Twin" title="Try to beat the detector" subtitle="Describe how a fraudster might change tactics. Axon simulates it on a copy of the data and shows what it catches." actions={<Mascot size={80} mood={mood} />} />

      <Card style={{ marginBottom: 20 }}>
        <div className="row-flex" style={{ marginBottom: howOpen ? 18 : 0 }}>
          <h2>How the Fraud Twin works</h2>
          <span className="small muted">It follows along as you run an attack below.</span>
          <span className="spacer" />
          <Button size="sm" variant="ghost" icon={howOpen ? 'less' : 'add'} onClick={() => setHowOpen(v => !v)}>{howOpen ? 'Hide' : 'Show'}</Button>
        </div>
        {howOpen && <TwinFlow s={{
          text, recipes: scenarios.length, busy, run,
          recipe: parsed && spec ? { name: spec.name, params: Object.entries(parsed.params) } : null,
          change: advice?.suggested_change ?? null,
          hardened: hardened && run ? { before: hardened.before?.detection_rate ?? run.detection_rate, after: hardened.after?.detection_rate ?? hardened.detection_rate } : null,
        }} />}
      </Card>

      <div className="home-grid twin-row" style={{ marginBottom: 20 }}>
        <Card>
          <div className="field">
            <label htmlFor="scheme">What if…</label>
            <textarea id="scheme" className="textarea" style={{ minHeight: 80 }} value={text} onChange={e => setText(e.target.value)} maxLength={600} />
          </div>
          <div className="chip-group" style={{ marginTop: 12 }}>
            {scenarios.slice(0, 3).map(s => <Chip key={s.id} onClick={() => setText(s.examples[0])}>{s.name}</Chip>)}
          </div>
          <div className="row-flex" style={{ marginTop: 16 }}>
            <Button icon="ai" loading={busy === 'parse'} onClick={build}>Build the attack</Button>
            <select className="select" style={{ width: 'auto' }} value="" onChange={e => { const s = scenarios.find(x => x.id === e.target.value); if (s) { setParsed({ scenario: s.id, params: Object.fromEntries(Object.entries(s.params).map(([k, v]) => [k, v.default])) }); setMsg(null); reset(); } }} aria-label="Pick a scheme">
              <option value="" disabled>or pick a scheme</option>
              {scenarios.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          {msg && <div style={{ marginTop: 14 }}><Note tone="warn">{msg}</Note></div>}
          {parsed && spec && (
            <motion.div className="help-panel" style={{ marginTop: 16 }} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={spring}>
              <h4>{spec.name}</h4>
              <div className="grid-3">
                {Object.entries(spec.params).map(([k, p]) => (
                  <div key={k} className="field">
                    <label className="xs muted" style={{ fontWeight: 600 }}>{k.replace(/_/g, ' ')}</label>
                    {p.type === 'bool' || p.type === 'enum' ? (
                      <select className="select" value={String(parsed.params[k])} onChange={e => setParsed({ ...parsed, params: { ...parsed.params, [k]: p.type === 'bool' ? e.target.value === 'true' : e.target.value } })}>
                        {(p.type === 'bool' ? ['true', 'false'] : p.values ?? []).map(v => <option key={v} value={v}>{p.type === 'bool' ? (v === 'true' ? 'yes' : 'no') : v}</option>)}
                      </select>
                    ) : (
                      <input className="input" type="number" min={p.min} max={p.max} step={p.type === 'float' ? 0.05 : 1} value={Number(parsed.params[k])}
                        onChange={e => setParsed({ ...parsed, params: { ...parsed.params, [k]: Math.min(Math.max(Number(e.target.value), p.min ?? -Infinity), p.max ?? Infinity) } })} />
                    )}
                  </div>
                ))}
              </div>
              <div className="row-flex" style={{ marginTop: 14 }}><Button icon="play" loading={busy === 'run'} onClick={go}>Run it</Button><span className="small muted">Runs on a copy. Your real queue is never touched.</span></div>
            </motion.div>
          )}
        </Card>
        <JudgeQr />
      </div>

      {run && <Results run={run} />}

      {run && run.missed > 0 && (
        <Card className="card-accent" style={{ marginTop: 20 }}>
          <div className="card-title"><span className="row-icon"><Icon name="wrench" size={15} /></span><h2>Make it stronger</h2></div>
          {busy === 'advise' ? <Skeleton h={70} /> : !advice?.suggested_change ? <p className="muted">{advice?.explanation ?? 'Nothing obvious to tune.'}</p> : (
            <div className="stack">
              <p>{advice.explanation}</p>
              <div className="row-flex">
                <span className="engine-pill on">{advice.suggested_change.param.replace(/_/g, ' ').toLowerCase()}: {advice.suggested_change.old_value} → {advice.suggested_change.new_value}</span>
                <span className="spacer" />
                <Button icon="accept" loading={busy === 'harden'} disabled={!!hardened} onClick={harden}>Approve and re-run</Button>
              </div>
              {hardened && <Compare before={run} after={hardened} />}
            </div>
          )}
        </Card>
      )}
    </>
  );
}

function Results({ run }: { run: TwinRun }) {
  return (
    <div className="home-grid twin-row">
      <Card>
        <div className="rec-head" style={{ marginBottom: 18 }}>
          <Ring value={run.detection_rate * 100} size={96} label={`Caught ${pct(run.detection_rate, 1)}`}>
            <div style={{ textAlign: 'center', lineHeight: 1.1 }}><div style={{ fontSize: '1.3rem' }}>{pct(run.detection_rate, 0)}</div><div style={{ fontSize: '.6rem', color: 'var(--text-3)', fontWeight: 650 }}>CAUGHT</div></div>
          </Ring>
          <div>
            <h2>{num(run.detected)} of {num(run.generated)} fake claims caught</h2>
            <p className="muted small">False alarms on real claims: {pct(run.false_positive_rate.run, 1)} (normally {pct(run.false_positive_rate.baseline, 1)})</p>
          </div>
        </div>
        <div className="stack">{Object.entries(run.by_layer).map(([k, v]) => <Bar key={k} label={METHOD_LABEL[k] ?? k} value={v} max={run.generated} right={num(v)} />)}</div>
        {run.miss_reason_summary.length > 0 && (
          <div className="help-panel" style={{ marginTop: 16 }}>
            <h4>Why {num(run.missed)} slipped through</h4>
            {run.miss_reason_summary.map(m => <p key={m.reason_code} className="small">{m.count} claims: {m.reason_code === 'TEMPORAL_WINDOW' ? `spread over about ${m.typical_value} days, longer than the ${m.threshold}-day window` : m.reason_code === 'BELOW_HUG_SHARE' ? `only ${pct(m.typical_value)} of claims near the limit, under the ${pct(m.threshold)} trigger` : m.reason_code.replace(/_/g, ' ').toLowerCase()}</p>)}
          </div>
        )}
      </Card>
      <Card className="graph-card" style={{ padding: 0 }}>
        <div className="pad"><h2>The fake network</h2></div>
        {run.injected_graph.nodes.length
          ? <div className="graph-slot"><NetworkGraph nodes={run.injected_graph.nodes} edges={run.injected_graph.edges} injectedIds={new Set(run.injected_graph.nodes.map(n => n.id))} /></div>
          : <p className="pad muted">No network for this scheme.</p>}
      </Card>
    </div>
  );
}

function Compare({ before, after }: { before: TwinRun; after: TwinRun }) {
  const b = after.before ?? { detection_rate: before.detection_rate, false_positive_rate: before.false_positive_rate.run };
  const a = after.after ?? { detection_rate: after.detection_rate, false_positive_rate: after.false_positive_rate.run };
  return (
    <div className="stats">
      <div className="stat"><b>{pct(b.detection_rate, 1)} → {pct(a.detection_rate, 1)}</b><span>caught</span></div>
      <div className="stat"><b>{pct(b.false_positive_rate, 1)} → {pct(a.false_positive_rate, 1)}</b><span>false alarms</span></div>
    </div>
  );
}

function JudgeQr() {
  const local = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(window.location.hostname);
  const at = (host: string) => `${window.location.protocol}//${host}${window.location.port ? `:${window.location.port}` : ''}/challenge`;
  const [url, setUrl] = useState(() => at(window.location.hostname));
  const [ips, setIps] = useState<string[]>([]);
  const [svg, setSvg] = useState('');
  // Opened on this laptop: swap localhost for its Wi-Fi address so a phone on the same network can reach it.
  useEffect(() => {
    if (!local) return;
    ai.lan().then(r => { if (r.ip) setUrl(at(r.ip)); setIps(r.candidates); }).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { QRCode.toString(url, { type: 'svg', margin: 1, width: 170, color: { dark: '#1d1d1f', light: '#ffffff' } }).then(setSvg).catch(() => setSvg('')); }, [url]);
  const host = (() => { try { return new URL(url).hostname; } catch { return ''; } })();
  return (
    <Card className="qr-card">
      <div className="card-title"><span className="row-icon"><Icon name="qr-code" size={15} /></span><h2>Judges, try it</h2></div>
      <div className="qr-slot" dangerouslySetInnerHTML={{ __html: svg }} />
      <input className="input mono" value={url} onChange={e => setUrl(e.target.value)} aria-label="Challenge link" />
      {ips.length > 1 && (
        <select className="select" style={{ marginTop: 8 }} value={ips.includes(host) ? host : ''} onChange={e => setUrl(at(e.target.value))} aria-label="Network address">
          {!ips.includes(host) && <option value="">Custom address</option>}
          {ips.map((ip, i) => <option key={ip} value={ip}>{ip}{i === 0 ? ' · Wi-Fi (recommended)' : ''}</option>)}
        </select>
      )}
      <p className="xs faint" style={{ marginTop: 6 }}>
        {/localhost|127\.0\.0\.1/.test(url) ? 'Phones need this laptop’s Wi-Fi address instead of localhost.' : 'Scan with a phone on the same Wi-Fi as this laptop.'}
      </p>
    </Card>
  );
}

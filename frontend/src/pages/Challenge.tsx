import { motion } from 'motion/react';
import { useEffect, useRef, useState } from 'react';
import { Mascot, MascotMark } from '../components/Mascot';
import { Bar, Button, Card, Note } from '../components/ui';
import { ai, api } from '../lib/api';
import { METHOD_LABEL, num, pct } from '../lib/format';
import { useAsync } from '../lib/hooks';
import { spring } from '../lib/theme';
import type { TwinRun } from '../lib/types';

/** Phone page opened from the QR code: a judge types a scheme and sees whether Axon catches it. */
export function Challenge() {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [typing, setTyping] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [run, setRun] = useState<TwinRun | null>(null);
  const [demo, setDemo] = useState(0);
  const timer = useRef<number>();
  const sc = useAsync(() => api.twinScenarios(), []);
  // The engine's own example schemes (the same ones the Fraud Twin page offers on the laptop).
  const examples: string[] = (sc.data?.scenarios ?? []).flatMap(s => s.examples);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const go = async (scheme = text) => {
    setBusy(true); setMsg(null); setRun(null);
    try {
      const p = await ai.twinParse(scheme);
      if (!p.supported || !p.scenario) { setMsg(p.reason ?? "I can't simulate that one yet. We've noted it."); return; }
      setRun(await api.twinRun(p.scenario, p.params ?? {}));
    } catch (e) { setMsg(`Couldn't reach Axon (${(e as Error).message}).`); }
    finally { setBusy(false); }
  };

  /** One tap: type the next example scheme into the box, then run it. */
  const typeDemo = () => {
    if (!examples.length) return;
    const ex = examples[demo % examples.length];
    setDemo(d => d + 1); setRun(null); setMsg(null); setText(''); setTyping(true);
    let i = 0;
    const step = () => {
      i = Math.min(ex.length, i + 2);
      setText(ex.slice(0, i));
      if (i < ex.length) timer.current = window.setTimeout(step, 35);
      else { setTyping(false); void go(ex); }
    };
    timer.current = window.setTimeout(step, 150);
  };

  return (
    <div className="judge-shell">
      <div className="judge-card stack-lg">
        <div className="brand"><MascotMark size={30} />Axon</div>
        <div className="row-flex" style={{ alignItems: 'flex-end' }}>
          <Mascot size={78} mood={busy || typing ? 'thinking' : run ? 'happy' : 'watching'} />
          <div className="bubble">Think like a fraudster. Can you get past me?</div>
        </div>
        <Card>
          <div className="field">
            <label htmlFor="j">Describe a billing scheme</label>
            <textarea id="j" className={`textarea ${typing ? 'is-typing' : ''}`} value={text} onChange={e => setText(e.target.value)} maxLength={600}
              readOnly={typing} placeholder="e.g. Three clinics split ₹3 lakh surgeries into ₹45,000 claims" />
          </div>
          <div className="stack" style={{ marginTop: 14 }}>
            <Button size="lg" block icon="ai" variant="tinted" loading={typing} disabled={busy || !examples.length} onClick={typeDemo}>
              {demo ? 'Type another demo scheme' : 'Type a demo scheme for me'}
            </Button>
            <Button size="lg" block icon="play" loading={busy} disabled={!text.trim() || typing} onClick={() => go()}>Try it</Button>
          </div>
        </Card>
        {msg && <Note tone="warn">{msg}</Note>}
        {run && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={spring}>
            <Card className="card-accent">
              <p className="eyebrow">Axon caught</p>
              <h1>{pct(run.detection_rate, 0)}</h1>
              <p className="muted">{num(run.detected)} of {num(run.generated)} fake claims</p>
              <div className="stack" style={{ marginTop: 16 }}>{Object.entries(run.by_layer).map(([k, v]) => <Bar key={k} label={METHOD_LABEL[k] ?? k} value={v} max={run.generated} right={num(v)} />)}</div>
              <p className="xs faint" style={{ marginTop: 14 }}>Simulated on synthetic data. Watch the big screen for what happens next.</p>
            </Card>
          </motion.div>
        )}
      </div>
    </div>
  );
}

import { motion } from 'motion/react';
import { useState } from 'react';
import { Mascot, MascotMark } from '../components/Mascot';
import { Bar, Button, Card, Note } from '../components/ui';
import { ai, api } from '../lib/api';
import { METHOD_LABEL, num, pct } from '../lib/format';
import { spring } from '../lib/theme';
import type { TwinRun } from '../lib/types';

/** Phone page opened from the QR code: a judge types a scheme and sees whether Axon catches it. */
export function Challenge() {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [run, setRun] = useState<TwinRun | null>(null);

  const go = async () => {
    setBusy(true); setMsg(null); setRun(null);
    try {
      const p = await ai.twinParse(text);
      if (!p.supported || !p.scenario) { setMsg(p.reason ?? "I can't simulate that one yet. We've noted it."); return; }
      setRun(await api.twinRun(p.scenario, p.params ?? {}));
    } catch (e) { setMsg(`Couldn't reach Axon (${(e as Error).message}).`); }
    finally { setBusy(false); }
  };

  return (
    <div className="judge-shell">
      <div className="judge-card stack-lg">
        <div className="brand"><MascotMark size={30} />Axon</div>
        <div className="row-flex" style={{ alignItems: 'flex-end' }}>
          <Mascot size={78} mood={busy ? 'thinking' : run ? 'happy' : 'watching'} />
          <div className="bubble">Think like a fraudster. Can you get past me?</div>
        </div>
        <Card>
          <div className="field">
            <label htmlFor="j">Describe a billing scheme</label>
            <textarea id="j" className="textarea" value={text} onChange={e => setText(e.target.value)} maxLength={600} placeholder="e.g. Three clinics split ₹3 lakh surgeries into ₹45,000 claims" />
          </div>
          <div style={{ marginTop: 14 }}><Button size="lg" block icon="play" loading={busy} disabled={!text.trim()} onClick={go}>Try it</Button></div>
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

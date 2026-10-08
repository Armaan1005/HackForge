import { motion } from 'motion/react';
import { FlaskConical, Waypoints } from 'lucide-react';
import { useState } from 'react';
import { Banner, Button, Card } from '../components/ui';
import { ai, api } from '../lib/api';
import { METHOD_LABEL, num, pct } from '../lib/format';
import type { TwinRun } from '../lib/types';

/** Mobile page opened from the QR code: a judge types a scheme and sees whether Axon catches it. */
export function Challenge() {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [scenario, setScenario] = useState<string | null>(null);
  const [run, setRun] = useState<TwinRun | null>(null);

  const go = async () => {
    setBusy(true); setMsg(null); setRun(null); setScenario(null);
    try {
      const p = await ai.twinParse(text);
      if (!p.supported || !p.scenario) { setMsg(p.reason ?? 'That scheme is not supported yet. We logged it as a new pattern to model.'); return; }
      setScenario(p.scenario_name ?? p.scenario);
      setRun(await api.twinRun(p.scenario, p.params ?? {}));
    } catch (e) { setMsg(`Couldn't reach Axon (${(e as Error).message}).`); }
    finally { setBusy(false); }
  };

  return (
    <div className="judge-shell">
      <div className="judge-card stack">
        <div className="row-nw" style={{ gap: 10 }}><span className="brand-mark"><Waypoints size={16} /></span><b style={{ fontSize: '1.1rem' }}>Axon · Judge challenge</b></div>
        <Card>
          <div className="stack">
            <h2>Try to beat the detector.</h2>
            <p className="small muted">Describe how a fraudster might bill a health insurer. Axon will simulate it on synthetic data and try to catch it.</p>
            <textarea className="textarea" value={text} onChange={e => setText(e.target.value)} maxLength={600} placeholder="e.g. What if three clinics split ₹3 lakh surgeries into ₹45,000 claims?" />
            <Button size="lg" block icon={FlaskConical} loading={busy} onClick={go} disabled={!text.trim()}>Run it</Button>
          </div>
        </Card>
        {msg && <Banner tone="warn">{msg}</Banner>}
        {run && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <Card>
              <div className="xs faint">{scenario}</div>
              <div className="stat-value" style={{ fontSize: '3rem' }}>{pct(run.detection_rate, 1)}</div>
              <div className="small muted">caught · {num(run.detected)} of {num(run.generated)} synthetic claims</div>
              <div className="divider" />
              {Object.entries(run.by_layer).map(([k, v]) => <div key={k} className="row-nw between small"><span>{METHOD_LABEL[k] ?? k}</span><b>{num(v)}</b></div>)}
              {run.missed > 0 && <p className="small" style={{ marginTop: 10 }}>Missed {num(run.missed)}: {run.missed_claims[0]?.description}</p>}
              <p className="xs faint" style={{ marginTop: 10 }}>Sandbox simulation on synthetic data. Watch the big screen for the hardening rerun.</p>
            </Card>
          </motion.div>
        )}
      </div>
    </div>
  );
}

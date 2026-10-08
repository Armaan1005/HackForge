import { motion } from 'motion/react';
import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Icon, type IconName } from '../components/Icon';
import { Mascot, MascotMark } from '../components/Mascot';
import { fade, spring } from '../lib/theme';
import './landing.css';

const roles: { id: string; label: string; icon: IconName }[] = [
  { id: 'investigator', label: 'Investigator', icon: 'inspect' },
  { id: 'manager', label: 'SIU manager', icon: 'employee' },
  { id: 'analyst', label: 'Analyst', icon: 'bar-chart' },
];

/** Demo sign-in only: Axon runs on synthetic data and has no real accounts or auth backend.
 *  The chosen name/role is kept in sessionStorage so the app can greet the user. */
export function LoginForm({ back = true }: { back?: boolean }) {
  const nav = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('investigator');
  const [show, setShow] = useState(false);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!/^\S+@\S+\.\S+$/.test(email)) return setErr('Enter a valid work email.');
    if (password.length < 6) return setErr('Password must be at least 6 characters.');
    setErr('');
    setBusy(true);
    try { sessionStorage.setItem('axon.user', JSON.stringify({ email, role })); } catch { /* storage may be blocked */ }
    setTimeout(() => nav('/'), 600);
  };

  return (
    <motion.form className="auth-card stack" onSubmit={submit} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={spring} noValidate>
      <div>
        {back && <Link to="/welcome" className="small muted row-flex" style={{ gap: 6 }}><Icon name="slim-arrow-left" size={14} />Back</Link>}
        <h1>Welcome back</h1>
        <p className="muted">Sign in to your SIU workspace.</p>
      </div>

      <div className="field">
        <label>I am a</label>
        <div className="role-pick" role="radiogroup">
          {roles.map(r => (
            <button type="button" key={r.id} role="radio" aria-checked={role === r.id} className={role === r.id ? 'on' : ''} onClick={() => setRole(r.id)}>
              <Icon name={r.icon} size={18} />{r.label}
            </button>
          ))}
        </div>
      </div>

      <div className="field">
        <label htmlFor="email">Work email</label>
        <input id="email" className="input" type="email" autoComplete="username" placeholder="you@insurer.com" value={email} onChange={e => setEmail(e.target.value)} />
      </div>

      <div className="field">
        <div className="row-flex" style={{ justifyContent: 'space-between' }}>
          <label htmlFor="pw">Password</label>
          <a className="small" href="#" onClick={e => e.preventDefault()}>Forgot password?</a>
        </div>
        <div className="pw-wrap">
          <input id="pw" className="input" type={show ? 'text' : 'password'} autoComplete="current-password" placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} />
          <button type="button" className="eye" aria-label={show ? 'Hide password' : 'Show password'} onClick={() => setShow(v => !v)}>
            <Icon name={show ? 'hide' : 'inspect'} size={16} />
          </button>
        </div>
      </div>

      {err && <motion.div className="auth-err" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>{err}</motion.div>}

      <button className="btn btn-primary btn-lg btn-block" type="submit" disabled={busy}>
        {busy ? 'Signing in…' : <><Icon name="unlocked" size={16} />Sign in</>}
      </button>
      <div className="auth-or">or</div>
      <button type="button" className="btn btn-secondary btn-lg btn-block" onClick={() => nav('/')}>
        <Icon name="play" size={15} />Explore the demo without signing in
      </button>
      <p className="xs faint" style={{ textAlign: 'center' }}>Demo sign-in: no real accounts. Human review is required for every decision.</p>
    </motion.form>
  );
}

export function Login() {
  return (
    <div className="auth">
      <aside className="auth-side">
        <div className="glow" />
        <Link to="/welcome" className="brand" style={{ color: '#fff' }}><MascotMark size={30} />Axon</Link>
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={fade}>
          <Mascot size={120} mood="watching" />
          <p className="quote" style={{ marginTop: 22 }}>“One claim looks normal. Forty-seven connected claims don’t.”</p>
          <p className="muted-w" style={{ marginTop: 12 }}>Evidence-first fraud, waste &amp; abuse review for SIU teams.</p>
        </motion.div>
        <p className="muted-w small">All data in this demo is synthetic.</p>
      </aside>

      <main className="auth-main">
        <LoginForm />
      </main>
    </div>
  );
}

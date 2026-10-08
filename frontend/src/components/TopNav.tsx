import { motion } from 'motion/react';
import { CircleHelp, FlaskConical, LayoutGrid, ListOrdered, Moon, ShieldCheck, Sparkles, Sun, Waypoints } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { ai, useEngineSource } from '../lib/api';
import { useInterval } from '../lib/hooks';
import { spring, useTheme } from '../lib/theme';
import type { AiStatus } from '../lib/types';
import { HowItWorks } from './HowItWorks';
import { IconButton } from './ui';

const links = [
  { to: '/', label: 'Command', icon: LayoutGrid, end: true },
  { to: '/queue', label: 'SIU Queue', icon: ListOrdered },
  { to: '/explained', label: 'Explained', icon: Sparkles },
  { to: '/twin', label: 'Fraud Twin', icon: FlaskConical },
  { to: '/trust', label: 'Trust', icon: ShieldCheck },
];

export function Brand() {
  return (
    <Link to="/" className="brand" aria-label="Axon home">
      <span className="brand-mark"><Waypoints size={16} strokeWidth={2.4} /></span>
      Axon <small>SIU console</small>
    </Link>
  );
}

export function TopNav() {
  const { theme, toggle } = useTheme();
  const source = useEngineSource();
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [aiDown, setAiDown] = useState(false);
  const [help, setHelp] = useState(false);
  const poll = () => ai.status().then(s => { setStatus(s); setAiDown(false); }).catch(() => setAiDown(true));
  useInterval(poll, 8000);
  useEffect(() => { poll(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const aiLabel = aiDown ? 'AI service offline' : !status ? 'AI…' : status.enabled ? `Gemini · ${status.queue_depth} queued` : 'AI: templates';
  const aiDot = aiDown ? 'dot-off' : status?.enabled ? 'dot-live' : 'dot-warn';
  const aiTitle = status ? `Model ${status.model} · ${status.calls_this_minute}/${status.rpm_limit} calls this minute · ${status.cache_hits} cache hits · mode ${status.mode}` : 'Part B backend not reachable on :8000';

  return (
    <header className="topnav no-print">
      <div className="container topnav-inner">
        <Brand />
        <nav className="navlinks" aria-label="Main">
          {links.map(l => (
            <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => `navlink ${isActive ? 'active' : ''}`}>
              {({ isActive }) => (<>
                {isActive && <motion.span layoutId="nav-pill" className="nav-pill" transition={spring} />}
                <l.icon size={15} strokeWidth={2.1} /><span className="lbl">{l.label}</span>
              </>)}
            </NavLink>
          ))}
        </nav>
        <div className="nav-tools">
          <span className="chip" title={source === 'fixture' ? 'Engine API not up yet: showing the agreed contract fixtures' : 'Reading the live detection engine'}>
            <span className={`dot ${source === 'live' ? 'dot-live' : source === 'fixture' ? 'dot-warn' : 'dot-off'}`} />
            {source === 'live' ? 'Live engine' : source === 'fixture' ? 'Fixtures' : 'Engine…'}
          </span>
          <span className="chip" title={aiTitle}><span className={`dot ${aiDot}`} />{aiLabel}</span>
          <IconButton icon={CircleHelp} label="How Axon works" onClick={() => setHelp(true)} />
          <IconButton icon={theme === 'dark' ? Sun : Moon} label={theme === 'dark' ? 'Light mode' : 'Dark mode'} onClick={toggle} />
        </div>
      </div>
      <HowItWorks open={help} onClose={() => setHelp(false)} />
    </header>
  );
}

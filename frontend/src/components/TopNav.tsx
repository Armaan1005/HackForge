import { motion } from 'motion/react';
import { CircleHelp, FlaskConical, LayoutGrid, ListOrdered, ShieldCheck, Sparkles, Waypoints } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { ai, useEngineSource } from '../lib/api';
import { useInterval } from '../lib/hooks';
import { spring } from '../lib/theme';
import type { AiStatus } from '../lib/types';
import { HowItWorks } from './HowItWorks';
import { IconButton } from './ui';

const links = [
  { to: '/', label: 'Today', icon: LayoutGrid, end: true },
  { to: '/queue', label: 'Queue', icon: ListOrdered },
  { to: '/explained', label: 'Explained', icon: Sparkles },
  { to: '/twin', label: 'Fraud Twin', icon: FlaskConical },
  { to: '/trust', label: 'Trust', icon: ShieldCheck },
];

export function TopNav() {
  const source = useEngineSource();
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [aiDown, setAiDown] = useState(false);
  const [help, setHelp] = useState(false);
  const poll = () => ai.status().then(s => { setStatus(s); setAiDown(false); }).catch(() => setAiDown(true));
  useInterval(poll, 8000);
  useEffect(() => { poll(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const healthy = source === 'live' && status?.enabled && !aiDown;
  const title = [
    source === 'live' ? 'Engine: live' : 'Engine: contract fixtures',
    aiDown ? 'AI: backend offline' : status?.enabled ? `AI: ${status.model} · ${status.queue_depth} queued · ${status.calls_this_minute}/${status.rpm_limit} per min` : 'AI: templates (no key)',
  ].join('\n');

  return (
    <header className="topnav no-print">
      <div className="container topnav-inner">
        <Link to="/" className="brand" aria-label="Axon home"><span className="brand-mark"><Waypoints size={15} strokeWidth={2.4} /></span>Axon</Link>
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
          <span className="status-dot" title={title} aria-label={title}><span className={`dot ${healthy ? 'dot-live' : aiDown ? 'dot-off' : 'dot-warn'}`} /></span>
          <IconButton icon={CircleHelp} label="How Axon works" onClick={() => setHelp(true)} />
        </div>
      </div>
      <HowItWorks open={help} onClose={() => setHelp(false)} />
    </header>
  );
}

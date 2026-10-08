import { motion } from 'motion/react';
import { useEffect, useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { ai, useEngineSource } from '../lib/api';
import { useInterval } from '../lib/hooks';
import { spring } from '../lib/theme';
import type { AiStatus } from '../lib/types';
import { HowItWorks } from './HowItWorks';
import { Icon, type IconName } from './Icon';
import { MascotMark } from './Mascot';
import { Avatar, IconButton } from './ui';

export const INVESTIGATOR = { name: 'Priya Sharma', role: 'SIU investigator' };

const links: { to: string; label: string; icon: IconName; end?: boolean }[] = [
  { to: '/', label: 'Home', icon: 'home', end: true },
  { to: '/queue', label: 'Cases', icon: 'workflow-tasks' },
  { to: '/court', label: 'Evidence Court', icon: 'decision' },
  { to: '/explained', label: 'Explained', icon: 'complete' },
  { to: '/twin', label: 'Fraud Twin', icon: 'lab' },
  { to: '/trust', label: 'Trust', icon: 'shield' },
];

export function TopNav() {
  const source = useEngineSource();
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [help, setHelp] = useState(false);
  const [menu, setMenu] = useState(false);
  const poll = () => ai.status().then(setStatus).catch(() => setStatus(null));
  useInterval(poll, 8000);
  useEffect(() => { poll(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const aiOn = !!status?.enabled;
  return (
    <header className="topnav no-print">
      <div className="container topnav-inner">
        <Link to="/" className="brand" aria-label="Axon home"><MascotMark size={30} />Axon <small>for SIU teams</small></Link>
        <nav className="navlinks" aria-label="Main">
          {links.map(l => (
            <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => `navlink ${isActive ? 'active' : ''}`}>
              {({ isActive }) => (<>
                {isActive && <motion.span layoutId="nav-pill" className="nav-pill" transition={spring} />}
                <Icon name={l.icon} size={15} /><span className="lbl">{l.label}</span>
              </>)}
            </NavLink>
          ))}
        </nav>
        <div className="nav-tools">
          <span className={`engine-pill ${aiOn ? 'on' : ''}`} title={`${source === 'live' ? 'Live detection engine' : 'Sample data (engine not connected yet)'} · ${status ? `${status.model}, ${status.mode}` : 'AI service offline'}`}>
            <Icon name="ai" size={13} />{!aiOn ? 'AI templates' : status?.model.startsWith('ollama/') ? 'Local AI on' : 'Gemini on'}
          </span>
          <IconButton icon="sys-help" label="How Axon works" onClick={() => setHelp(true)} />
          <div style={{ position: 'relative' }}>
            <button className="icon-btn" style={{ width: 'auto', padding: 3 }} aria-label="Account" aria-expanded={menu} onClick={() => setMenu(v => !v)}>
              <Avatar name={INVESTIGATOR.name} hue={158} size={32} />
            </button>
            {menu && (
              <motion.div className="card" style={{ position: 'absolute', right: 0, top: 46, width: 240, padding: 8, zIndex: 60 }}
                initial={{ opacity: 0, y: -6, scale: .98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={spring} onMouseLeave={() => setMenu(false)}>
                <div style={{ padding: '8px 10px' }}><b>{INVESTIGATOR.name}</b><div className="small muted">{INVESTIGATOR.role}</div></div>
                <div className="divider" style={{ margin: '6px 0' }} />
                <div className="small muted" style={{ padding: '4px 10px' }}>{source === 'live' ? 'Connected to the live engine' : 'Using sample data'}</div>
                <button className="btn btn-ghost btn-sm btn-block" style={{ justifyContent: 'flex-start' }} onClick={() => { setMenu(false); setHelp(true); }}><Icon name="sys-help" size={15} />How Axon works</button>
              </motion.div>
            )}
          </div>
        </div>
      </div>
      <HowItWorks open={help} onClose={() => setHelp(false)} />
    </header>
  );
}

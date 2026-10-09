import { motion } from 'motion/react';
import { useLayoutEffect, useRef, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { useEngineSource } from '../lib/api';
import { spring } from '../lib/theme';
import { HowItWorks } from './HowItWorks';
import { Icon, type IconName } from './Icon';
import { MascotMark } from './Mascot';
import { Avatar, IconButton } from './ui';

export const INVESTIGATOR = { name: 'Priya Sharma', role: 'SIU investigator' };

const links: { to: string; label: string; icon: IconName; end?: boolean }[] = [
  { to: '/home', label: 'Home', icon: 'home', end: true },
  { to: '/queue', label: 'Cases', icon: 'workflow-tasks' },
  { to: '/explained', label: 'Explained', icon: 'complete' },
  { to: '/court', label: 'Evidence Court', icon: 'decision' },
  { to: '/twin', label: 'Fraud Twin', icon: 'lab' },
  { to: '/timelines', label: 'Timelines', icon: 'history' },
  { to: '/rulebook', label: 'Rulebook', icon: 'course-book' },
  { to: '/trust', label: 'Trust', icon: 'shield' },
];

// Each page renders its own TopNav, so the pill's last position lives outside the component: the new nav starts
// the pill where the old one left it, then glides to the active link (CSS transition, no layout animation).
let lastPill: { x: number; w: number } | null = null;

export function TopNav() {
  const navRef = useRef<HTMLElement>(null);
  const { pathname } = useLocation();
  const [pill, setPill] = useState(lastPill);
  useLayoutEffect(() => {
    const measure = () => {
      const a = navRef.current?.querySelector<HTMLElement>('.navlink.active');
      const next = a ? { x: a.offsetLeft, w: a.offsetWidth } : null;
      lastPill = next;
      requestAnimationFrame(() => setPill(next));
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (navRef.current) ro.observe(navRef.current);
    return () => ro.disconnect();
  }, [pathname]);
  const source = useEngineSource();
  const [help, setHelp] = useState(false);
  const [menu, setMenu] = useState(false);

  return (
    <header className="topnav no-print">
      <div className="container topnav-inner">
        <Link to="/" className="brand" aria-label="Axon home"><MascotMark size={30} />Axon <small>for SIU teams</small></Link>
        <nav ref={navRef} className="navlinks" aria-label="Main">
          {pill && <span className="nav-pill" style={{ transform: `translateX(${pill.x}px)`, width: pill.w }} aria-hidden />}
          {links.map(l => (
            <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => `navlink ${isActive ? 'active' : ''}`}>
              <Icon name={l.icon} size={15} /><span className="lbl">{l.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="nav-tools">
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

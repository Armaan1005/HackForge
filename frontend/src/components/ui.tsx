import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useLayoutEffect, useRef, useState, type ButtonHTMLAttributes, type CSSProperties, type MouseEvent, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { STATUS } from '../lib/format';
import { fade, spring } from '../lib/theme';
import { Icon, type IconName } from './Icon';
import { Mascot } from './Mascot';

// ── Button ──────────────────────────────────────────────────────────────────
// Tactile: lifts on hover, presses in on tap, ripples from the pointer.
type BtnProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'onDrag' | 'onDragStart' | 'onDragEnd' | 'onAnimationStart'> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'tinted';
  size?: 'sm' | 'md' | 'lg'; icon?: IconName; iconRight?: IconName; loading?: boolean; block?: boolean;
};
export function Button({ variant = 'primary', size = 'md', icon, iconRight, loading, block, className = '', children, onClick, disabled, ...rest }: BtnProps) {
  const [ripples, setRipples] = useState<{ id: number; x: number; y: number }[]>([]);
  const click = (e: MouseEvent<HTMLButtonElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const id = Date.now();
    setRipples(list => [...list, { id, x: e.clientX - r.left, y: e.clientY - r.top }]);
    setTimeout(() => setRipples(list => list.filter(x => x.id !== id)), 650);
    onClick?.(e);
  };
  return (
    <motion.button {...rest} disabled={disabled || loading} onClick={click}
      className={`btn btn-${variant} btn-${size} ${block ? 'btn-block' : ''} ${className}`}
      whileHover={disabled ? undefined : { y: -1.5 }} whileTap={disabled ? undefined : { scale: 0.965, y: 0 }} transition={spring}>
      {ripples.map(r => <span key={r.id} className="ripple" style={{ left: r.x, top: r.y }} />)}
      {loading ? <span className="spinner" aria-hidden /> : icon && <Icon name={icon} size={size === 'lg' ? 20 : 16} />}
      {children && <span className="btn-label">{children}</span>}
      {iconRight && !loading && <Icon name={iconRight} size={size === 'lg' ? 18 : 14} />}
    </motion.button>
  );
}

export function IconButton({ icon, label, active, onClick, size = 18 }: { icon: IconName; label: string; active?: boolean; onClick?: () => void; size?: number }) {
  return (
    <motion.button type="button" aria-label={label} title={label} aria-pressed={active} className={`icon-btn ${active ? 'is-active' : ''}`}
      onClick={onClick} whileHover={{ scale: 1.06 }} whileTap={{ scale: 0.9 }} transition={spring}>
      <Icon name={icon} size={size} />
    </motion.button>
  );
}

// ── Segmented control with sliding pill ─────────────────────────────────────
export function Segmented<T extends string | number>({ value, onChange, options, label, size = 'md' }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode; icon?: IconName }[]; label: string; size?: 'sm' | 'md';
}) {
  // One indicator that measures the active button and glides to it (position + width, no scaling),
  // so the rounded corners never stretch mid-animation.
  const box = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ x: number; w: number } | null>(null);
  const idx = options.findIndex(o => o.value === value);
  useLayoutEffect(() => {
    const measure = () => {
      const b = box.current?.querySelectorAll<HTMLButtonElement>(':scope > button')[idx];
      if (b) setPos({ x: b.offsetLeft, w: b.offsetWidth });
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (box.current) ro.observe(box.current);
    return () => ro.disconnect();
  }, [idx, options.length]);
  return (
    <div ref={box} className={`segmented seg-${size}`} role="radiogroup" aria-label={label}>
      {pos && <span className="seg-pill" style={{ transform: `translateX(${pos.x}px)`, width: pos.w }} />}
      {options.map(o => (
        <button key={String(o.value)} type="button" role="radio" aria-checked={value === o.value} className={value === o.value ? 'active' : ''} onClick={() => onChange(o.value)}>
          <span className="seg-content">{o.icon && <Icon name={o.icon} size={14} />}{o.label}</span>
        </button>
      ))}
    </div>
  );
}

// ── Card with pointer spotlight ─────────────────────────────────────────────
export function Card({ children, className = '', interactive, onClick, style }: { children: ReactNode; className?: string; interactive?: boolean; onClick?: () => void; style?: CSSProperties }) {
  const ref = useRef<HTMLDivElement>(null);
  const move = (e: MouseEvent) => {
    if (!interactive || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    ref.current.style.setProperty('--mx', `${e.clientX - r.left}px`);
    ref.current.style.setProperty('--my', `${e.clientY - r.top}px`);
  };
  return (
    <motion.div ref={ref} style={style} onMouseMove={move} onClick={onClick}
      onKeyDown={onClick ? e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } } : undefined}
      tabIndex={onClick ? 0 : undefined} role={onClick ? 'button' : undefined}
      className={`card ${interactive ? 'card-interactive' : ''} ${className}`}
      whileHover={interactive ? { y: -3 } : undefined} whileTap={interactive && onClick ? { scale: 0.985 } : undefined} transition={spring}>
      {children}
    </motion.div>
  );
}

export function CardTitle({ icon, title, action }: { icon?: IconName; title: ReactNode; action?: ReactNode }) {
  return (
    <div className="card-title">
      {icon && <span className="row-icon"><Icon name={icon} size={15} /></span>}
      <h2>{title}</h2>
      <span className="spacer" />
      {action}
    </div>
  );
}

// ── Chips, status, pills ────────────────────────────────────────────────────
export function Chip({ children, selected, onClick, icon, tone }: { children: ReactNode; selected?: boolean; onClick?: () => void; icon?: IconName; tone?: 'accent' | 'good' | 'warn' | 'bad' }) {
  if (!onClick) return <span className={`chip chip-static ${tone ? 'chip-' + tone : ''}`}>{icon && <Icon name={icon} size={13} />}{children}</span>;
  return (
    <motion.button type="button" aria-pressed={selected} className={`chip ${selected ? 'selected' : ''}`} onClick={onClick} whileTap={{ scale: 0.94 }} transition={spring}>
      {icon && <Icon name={icon} size={13} />}{children}
    </motion.button>
  );
}

export function Status({ value }: { value: string }) {
  return <span className={`status status-${value}`}><span className="status-dot" />{STATUS[value]?.label ?? value.replace(/_/g, ' ')}</span>;
}

export function Strength({ value }: { value: string }) {
  return <span className={`verdict verdict-${value}`}>{value === 'strong' ? 'Strong evidence' : value === 'moderate' ? 'Moderate evidence' : 'Weak evidence'}</span>;
}

export function RiskPill({ value }: { value: number }) {
  return <span className={`score-pill ${value >= 85 ? 'high' : value >= 60 ? 'mid' : ''}`} title={`Risk ${value} of 100`}>{value}</span>;
}

// ── Progress ring & bar ─────────────────────────────────────────────────────
export function Ring({ value, size = 72, stroke = 7, label, children }: { value: number; size?: number; stroke?: number; label?: string; children?: ReactNode }) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r;
  return (
    <div className="ring" style={{ width: size, height: size }} role="img" aria-label={label || `${Math.round(value)} percent`}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} strokeWidth={stroke} className="ring-track" />
        <motion.circle cx={size / 2} cy={size / 2} r={r} strokeWidth={stroke} className="ring-fill" strokeDasharray={c}
          initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - Math.min(100, Math.max(0, value)) / 100) }}
          transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }} />
      </svg>
      <div className="ring-center">{children ?? Math.round(value)}</div>
    </div>
  );
}

export function Bar({ value, label, right, detail, max = 100 }: { value: number; label: ReactNode; right?: ReactNode; detail?: ReactNode; max?: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="bar">
      <div className="bar-head"><span>{label}</span><span className="tabular">{right ?? `${Math.round(pct)}%`}</span></div>
      <div className="bar-track"><motion.div className="bar-fill" initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }} /></div>
      {detail}
    </div>
  );
}

// ── Sheet / modal ───────────────────────────────────────────────────────────
export function Sheet({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', esc);
    document.body.style.overflow = 'hidden';
    return () => { window.removeEventListener('keydown', esc); document.body.style.overflow = ''; };
  }, [open, onClose]);
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div className="sheet-backdrop" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <motion.div className={`sheet ${wide ? 'sheet-wide' : ''}`} role="dialog" aria-modal="true" aria-label={title} onClick={e => e.stopPropagation()}
            initial={{ y: 40, opacity: 0, scale: 0.98 }} animate={{ y: 0, opacity: 1, scale: 1 }} exit={{ y: 30, opacity: 0 }} transition={spring}>
            <div className="sheet-head"><h2>{title}</h2><IconButton icon="decline" label="Close" onClick={onClose} /></div>
            <div className="sheet-body">{children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

// ── Misc ────────────────────────────────────────────────────────────────────
const hueOf = (s: string) => [...s].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) % 360, 7);
export function Avatar({ name, size = 40, hue }: { name: string; size?: number; hue?: number }) {
  const initials = name.replace(/^(Dr\.?|R\.)\s+/i, '').split(/[\s&]+/).filter(Boolean).map(s => s[0]).join('').slice(0, 2).toUpperCase();
  return <span className="avatar" style={{ width: size, height: size, fontSize: size * 0.38, '--h': hue ?? hueOf(name) } as CSSProperties}>{initials || '·'}</span>;
}

export function Section({ title, footer, children }: { title?: string; footer?: string; children: ReactNode }) {
  return (
    <section className="group">
      {title && <h3 className="group-title">{title}</h3>}
      <div className="group-body">{children}</div>
      {footer && <p className="group-footer">{footer}</p>}
    </section>
  );
}

export function Empty({ title, body, action, mood = 'rest' }: { title: string; body?: string; action?: ReactNode; mood?: 'rest' | 'happy' | 'watching' }) {
  return (
    <div className="empty">
      <Mascot size={96} mood={mood} />
      <h3>{title}</h3>
      {body && <p>{body}</p>}
      {action}
    </div>
  );
}

export function PageHeader({ eyebrow, title, subtitle, actions }: { eyebrow?: ReactNode; title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <motion.header className="page-header" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={fade}>
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {subtitle && <p className="subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </motion.header>
  );
}

export function Skeleton({ h = 120, style }: { h?: number; style?: CSSProperties }) {
  return <div className="skeleton" style={{ height: h, ...style }} />;
}

export function Note({ tone = 'good', icon, children }: { tone?: 'good' | 'warn'; icon?: IconName; children: ReactNode }) {
  return <div className={tone === 'good' ? 'fair-note' : 'warn-note'}><Icon name={icon ?? (tone === 'good' ? 'shield' : 'alert')} size={16} /><div>{children}</div></div>;
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <Card>
      <Empty title="Couldn't load this" body={error.message} mood="rest" action={onRetry && <Button variant="secondary" size="sm" icon="refresh" onClick={onRetry}>Try again</Button>} />
    </Card>
  );
}

export function Cite({ id, title }: { id: string; title?: string }) {
  return <span className="cite" title={title ?? `Evidence ${id}`}>{id}</span>;
}

/** Pointer-following tooltip for chart marks. */
export function useTooltip() {
  const [tip, setTip] = useState<{ x: number; y: number; content: ReactNode } | null>(null);
  const node = tip ? createPortal(<div className="tip" style={{ left: Math.min(tip.x + 14, window.innerWidth - 290), top: tip.y + 14 }}>{tip.content}</div>, document.body) : null;
  return {
    node,
    bind: (content: ReactNode) => ({
      onMouseMove: (e: React.MouseEvent) => setTip({ x: e.clientX, y: e.clientY, content }),
      onMouseLeave: () => setTip(null),
    }),
  };
}

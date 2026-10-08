import { AnimatePresence, motion } from 'motion/react';
import { AlertTriangle, CheckCircle2, Info, OctagonAlert, X, type LucideIcon } from 'lucide-react';
import { useEffect, useId, useState, type ButtonHTMLAttributes, type CSSProperties, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { STATUS } from '../lib/format';
import { spring } from '../lib/theme';

// ── Button ──────────────────────────────────────────────────────────────────
type BtnProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'onDrag' | 'onDragStart' | 'onDragEnd' | 'onAnimationStart'> & {
  variant?: 'primary' | 'secondary' | 'tinted' | 'ghost' | 'good' | 'bad' | 'warn';
  size?: 'sm' | 'md' | 'lg'; icon?: LucideIcon; loading?: boolean; block?: boolean;
};
export function Button({ variant = 'primary', size = 'md', icon: Icon, loading, block, className = '', children, disabled, ...rest }: BtnProps) {
  return (
    <motion.button {...rest} disabled={disabled || loading}
      className={`btn btn-${variant} btn-${size} ${block ? 'btn-block' : ''} ${className}`}
      whileHover={disabled ? undefined : { y: -1 }} whileTap={disabled ? undefined : { scale: 0.97 }} transition={spring}>
      {loading ? <span className="spinner" aria-hidden /> : Icon && <Icon size={size === 'lg' ? 18 : 15} strokeWidth={2.2} />}
      {children}
    </motion.button>
  );
}

export function IconButton({ icon: Icon, label, onClick, active }: { icon: LucideIcon; label: string; onClick?: () => void; active?: boolean }) {
  return (
    <motion.button type="button" className="icon-btn" aria-label={label} title={label} aria-pressed={active} onClick={onClick}
      whileTap={{ scale: 0.9 }} transition={spring} style={active ? { color: 'var(--accent)', background: 'var(--accent-soft)' } : undefined}>
      <Icon size={18} strokeWidth={2} />
    </motion.button>
  );
}

// ── Segmented control (sliding pill) ────────────────────────────────────────
export function Segmented<T extends string | number>({ value, onChange, options, label, size = 'md' }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode; icon?: LucideIcon }[]; label: string; size?: 'sm' | 'md';
}) {
  const id = useId();
  return (
    <div className={`segmented seg-${size}`} role="radiogroup" aria-label={label}>
      {options.map(o => (
        <button key={String(o.value)} type="button" role="radio" aria-checked={value === o.value}
          className={value === o.value ? 'active' : ''} onClick={() => onChange(o.value)}>
          {value === o.value && <motion.span layoutId={`seg-${id}`} className="seg-pill" transition={spring} />}
          <span className="seg-content">{o.icon && <o.icon size={14} />}{o.label}</span>
        </button>
      ))}
    </div>
  );
}

// ── Card ────────────────────────────────────────────────────────────────────
export function Card({ children, className = '', onClick, style, title, icon: Icon, action, tight }: {
  children: ReactNode; className?: string; onClick?: () => void; style?: CSSProperties;
  title?: ReactNode; icon?: LucideIcon; action?: ReactNode; tight?: boolean;
}) {
  return (
    <motion.div className={`card ${tight ? 'card-tight' : ''} ${onClick ? 'card-interactive' : ''} ${className}`} style={style} onClick={onClick}
      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}>
      {(title || action) && (
        <div className="card-head">
          <h3>{Icon && <Icon size={16} strokeWidth={2.2} style={{ color: 'var(--accent)' }} />}{title}</h3>
          {action}
        </div>
      )}
      {children}
    </motion.div>
  );
}

export function Stat({ label, value, sub, icon: Icon, tone }: { label: ReactNode; value: ReactNode; sub?: ReactNode; icon?: LucideIcon; tone?: 'bad' | 'good' | 'warn' }) {
  const color = tone === 'bad' ? 'var(--bad-text)' : tone === 'good' ? 'var(--good-text)' : tone === 'warn' ? 'var(--warn-text)' : undefined;
  return (
    <Card tight>
      <div className="stat-label">{Icon && <Icon size={14} />}{label}</div>
      <div className="stat-value" style={{ color }}>{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </Card>
  );
}

// ── Status / strength pills (always icon + label, never colour alone) ────────
export function StatusPill({ status }: { status: string }) {
  const s = STATUS[status] ?? { label: status.replace(/_/g, ' '), tone: 'neutral' as const };
  const Icon = s.tone === 'bad' ? OctagonAlert : s.tone === 'warn' ? AlertTriangle : s.tone === 'good' ? CheckCircle2 : Info;
  const cls = s.tone === 'bad' ? 'chip-bad' : s.tone === 'warn' ? 'chip-warn' : s.tone === 'good' ? 'chip-good' : s.tone === 'accent' ? 'chip-accent' : '';
  return <span className={`chip ${cls}`}><Icon size={12} strokeWidth={2.4} />{s.label}</span>;
}

export function StrengthPill({ strength }: { strength: string }) {
  const bars = strength === 'strong' ? 3 : strength === 'moderate' ? 2 : 1;
  return (
    <span className="chip chip-outline" title={`Evidence strength: ${strength}`}>
      <span style={{ display: 'inline-flex', gap: 2, alignItems: 'flex-end' }} aria-hidden>
        {[1, 2, 3].map(i => <span key={i} style={{ width: 3, height: 4 + i * 3, borderRadius: 2, background: i <= bars ? 'var(--text)' : 'var(--line-strong)' }} />)}
      </span>
      {strength}
    </span>
  );
}

export function SourceBadge({ source }: { source?: string }) {
  if (!source) return null;
  const map: Record<string, [string, string]> = {
    llm: ['chip-accent', 'Gemini'], template: ['', 'Template'], keywords: ['', 'Keyword match'],
    code: ['chip-good', 'Code-verified'], ai: ['chip-accent', 'AI-observed'], code_only: ['', 'Code checks only'],
  };
  const [cls, label] = map[source] ?? ['', source];
  return <span className={`chip ${cls}`}>{label}</span>;
}

// ── Risk ring ───────────────────────────────────────────────────────────────
export function RiskRing({ value, size = 64, label }: { value: number; size?: number; label?: string }) {
  const r = (size - 8) / 2, c = 2 * Math.PI * r;
  const color = 'var(--text)'; // magnitude, not status: neutral ink, the number carries the meaning
  return (
    <div className="risk-ring" style={{ width: size, height: size }} role="img" aria-label={`${label ?? 'Risk'} ${value} of 100`}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--bg-2)" strokeWidth={4} />
        <motion.circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={4} strokeLinecap="round"
          strokeDasharray={c} initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - value / 100) }} transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }} />
      </svg>
      <span className="val" style={{ fontSize: size * 0.3 }}>{value}</span>
    </div>
  );
}

// ── Banner ──────────────────────────────────────────────────────────────────
export function Banner({ tone = 'info', icon: Icon, children }: { tone?: 'info' | 'warn' | 'bad' | 'good'; icon?: LucideIcon; children: ReactNode }) {
  const I = Icon ?? (tone === 'warn' ? AlertTriangle : tone === 'bad' ? OctagonAlert : tone === 'good' ? CheckCircle2 : Info);
  const color = tone === 'warn' ? 'var(--warn-text)' : tone === 'bad' ? 'var(--bad-text)' : tone === 'good' ? 'var(--good-text)' : 'var(--accent)';
  return <div className={`banner ${tone !== 'info' ? 'banner-' + tone : ''}`}><I size={17} style={{ color }} /><div>{children}</div></div>;
}

// ── Sheet (modal) ───────────────────────────────────────────────────────────
export function Sheet({ open, onClose, title, children, footer, wide }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [open, onClose]);
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div className="sheet-backdrop" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <motion.div className={`sheet ${wide ? 'sheet-wide' : ''}`} role="dialog" aria-modal="true" onClick={e => e.stopPropagation()}
            initial={{ y: 30, opacity: 0, scale: 0.98 }} animate={{ y: 0, opacity: 1, scale: 1 }} exit={{ y: 20, opacity: 0 }} transition={spring}>
            <div className="sheet-head"><h2>{title}</h2><IconButton icon={X} label="Close" onClick={onClose} /></div>
            <div className="sheet-body">{children}</div>
            {footer && <div className="sheet-foot">{footer}</div>}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

// ── Tooltip (follows pointer) ───────────────────────────────────────────────
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

export function Skeleton({ h = 120, style }: { h?: number; style?: CSSProperties }) {
  return <div className="skeleton" style={{ height: h, ...style }} />;
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <Banner tone="bad">
      <div className="row between"><span><b>Couldn't load this.</b> {error.message}</span>{onRetry && <Button size="sm" variant="secondary" onClick={onRetry}>Retry</Button>}</div>
    </Banner>
  );
}

export function Cite({ id, title }: { id: string; title?: string }) {
  return <span className="cite" title={title ?? `Evidence ${id}`}>{id}</span>;
}

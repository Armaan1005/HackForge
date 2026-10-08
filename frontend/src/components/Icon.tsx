import { icons, type IconName } from '../lib/icons';

export function Icon({ name, size = 18, className, label, style }: { name: IconName; size?: number; className?: string; label?: string; style?: React.CSSProperties }) {
  return (
    <svg viewBox="0 0 16 16" width={size} height={size} className={'icon ' + (className || '')} style={style}
      role={label ? 'img' : undefined} aria-label={label} aria-hidden={label ? undefined : true} focusable="false">
      <path d={icons[name]} fill="currentColor" />
    </svg>
  );
}

export type { IconName };

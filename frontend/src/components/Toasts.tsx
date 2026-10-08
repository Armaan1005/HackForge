import { AnimatePresence, motion } from 'motion/react';
import { useSyncExternalStore } from 'react';
import { spring } from '../lib/theme';
import { Icon, type IconName } from './Icon';

type Toast = { id: number; title: string; body?: string; icon?: IconName };
let items: Toast[] = [];
const subs = new Set<() => void>();
const emit = () => subs.forEach(f => f());

/** Glass toast, top right (bottom on phones). Same pattern as the Prism app. */
export function toast(t: Omit<Toast, 'id'>) {
  const id = Date.now() + Math.random();
  items = [...items, { ...t, id }];
  emit();
  setTimeout(() => { items = items.filter(x => x.id !== id); emit(); }, 4200);
}

export function Toasts() {
  const list = useSyncExternalStore(cb => { subs.add(cb); return () => subs.delete(cb); }, () => items);
  return (
    <div className="toasts" aria-live="polite">
      <AnimatePresence>
        {list.map(t => (
          <motion.div key={t.id} className="toast" initial={{ opacity: 0, x: 30, scale: .96 }} animate={{ opacity: 1, x: 0, scale: 1 }} exit={{ opacity: 0, x: 30 }} transition={spring}>
            <span className="toast-icon"><Icon name={t.icon ?? 'accept'} size={18} /></span>
            <div><div className="toast-title">{t.title}</div>{t.body && <div className="toast-body">{t.body}</div>}</div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

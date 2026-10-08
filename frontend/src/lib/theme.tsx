// Single light theme (cream canvas, green accent). Kept as a module so motion presets live in one place.
export const spring = { type: 'spring' as const, stiffness: 420, damping: 34, mass: 0.8 };
export const fade = { duration: 0.28, ease: [0.22, 1, 0.36, 1] as [number, number, number, number] };

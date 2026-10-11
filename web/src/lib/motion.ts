import type { Transition, Variants } from "framer-motion";

export const spring: Transition = { type: "spring", stiffness: 380, damping: 30 };
export const softSpring: Transition = { type: "spring", stiffness: 160, damping: 22 };

/** Staggered entrance: put `variants={container}` on the parent and `variants={item}` on each child. */
export const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08, delayChildren: 0.04 } },
};
export const item: Variants = {
  hidden: { opacity: 0, y: 18, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: softSpring },
};

/** Tactile press for buttons. */
export const tap = { whileTap: { scale: 0.98 }, transition: spring } as const;

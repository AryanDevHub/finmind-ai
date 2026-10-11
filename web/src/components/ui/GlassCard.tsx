import clsx from "clsx";
import { motion, useMotionValue, useReducedMotion, useSpring, type HTMLMotionProps } from "framer-motion";
import { useRef, type MouseEvent } from "react";

interface Props extends HTMLMotionProps<"div"> {
  /** Subtle 3D tilt toward the cursor (disabled under prefers-reduced-motion). */
  tilt?: boolean;
  /** Cursor-following spotlight + illuminated border. */
  spotlight?: boolean;
}

/**
 * The base surface of the app: glass card, hairline border that turns cyan on hover, optional spotlight
 * that follows the cursor and optional 3D tilt. The cursor position is written straight to CSS variables
 * (no React re-render per mouse move).
 */
export function GlassCard({ tilt = false, spotlight = true, className, children, onMouseMove, onMouseLeave, style, ...rest }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const rx = useSpring(useMotionValue(0), { stiffness: 220, damping: 20 });
  const ry = useSpring(useMotionValue(0), { stiffness: 220, damping: 20 });

  const move = (e: MouseEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (el) {
      const r = el.getBoundingClientRect();
      const x = e.clientX - r.left;
      const y = e.clientY - r.top;
      el.style.setProperty("--mx", `${x}px`);
      el.style.setProperty("--my", `${y}px`);
      if (tilt && !reduce) { ry.set((x / r.width - 0.5) * 7); rx.set(-(y / r.height - 0.5) * 7); }
    }
    onMouseMove?.(e);
  };
  const leave = (e: MouseEvent<HTMLDivElement>) => { rx.set(0); ry.set(0); onMouseLeave?.(e); };

  return (
    <motion.div
      ref={ref}
      onMouseMove={move}
      onMouseLeave={leave}
      style={{ ...(tilt ? { rotateX: rx, rotateY: ry, transformPerspective: 900 } : {}), ...style }}
      className={clsx("glass", spotlight && "spotlight", className)}
      {...rest}
    >
      {children}
    </motion.div>
  );
}

import { useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

/**
 * Animates a number toward `target` with an ease-out curve. Re-targeting mid-flight continues from the
 * currently displayed value (no jump back to 0). Honours prefers-reduced-motion by snapping.
 * Pair with `.num` (tabular figures) so digits don't jitter.
 */
export function useCountUp(target: number, { duration = 1100 }: { duration?: number } = {}): number {
  const reduce = useReducedMotion();
  const [value, setValue] = useState(reduce ? target : 0);
  const from = useRef(reduce ? target : 0);

  useEffect(() => {
    if (reduce) { from.current = target; setValue(target); return; }
    const a = from.current;
    const t0 = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - t0) / duration);
      const v = a + (target - a) * (1 - Math.pow(1 - t, 4)); // easeOutQuart
      from.current = v;
      setValue(v);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration, reduce]);

  return value;
}

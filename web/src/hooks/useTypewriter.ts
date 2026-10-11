import { useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";

/**
 * Reveals `text` progressively. NOTE: this is a client-side reveal of a reply that has already arrived
 * in full (the API is request/response, not streaming), used to make long answers easier to read.
 */
export function useTypewriter(text: string, enabled: boolean, charsPerSecond = 220): { shown: string; done: boolean } {
  const reduce = useReducedMotion();
  const instant = !enabled || !!reduce;
  const [count, setCount] = useState(instant ? text.length : 0);

  useEffect(() => {
    if (instant) { setCount(text.length); return; }
    setCount(0);
    const t0 = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const n = Math.min(text.length, Math.floor(((now - t0) / 1000) * charsPerSecond));
      setCount(n);
      if (n < text.length) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [text, instant, charsPerSecond]);

  return { shown: text.slice(0, count), done: count >= text.length };
}

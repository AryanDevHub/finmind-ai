import clsx from "clsx";
import { motion, type HTMLMotionProps } from "framer-motion";
import { forwardRef } from "react";

interface Props extends HTMLMotionProps<"div"> {
  /** Optional 3D tilt (kept for API compatibility, disabled for clean Swiss aesthetic) */
  tilt?: boolean;
  /** Optional spotlight (kept for API compatibility) */
  spotlight?: boolean;
}

/**
 * Precision Institutional Card
 * Clean hairline border, subtle top inset highlight, and high-contrast dark slate surface.
 */
export const GlassCard = forwardRef<HTMLDivElement, Props>(function GlassCard(
  { className, children, tilt = false, spotlight = false, ...rest },
  ref
) {
  return (
    <motion.div
      ref={ref}
      className={clsx("glass", className)}
      {...rest}
    >
      {children}
    </motion.div>
  );
});

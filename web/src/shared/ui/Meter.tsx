import { motion, useReducedMotion } from "motion/react";
import { DURATION, EASE } from "../tokens";
import styles from "./meter.module.css";

/** A bar for a share between 0 and 1. It grows once when shown; with reduced motion it is drawn at full length. */
export function Meter({ value, colour, label }: { value: number; colour: string; label: string }) {
  const still = useReducedMotion();
  const v = Math.max(0, Math.min(1, value));
  return (
    <div className={styles.track} role="meter" aria-valuemin={0} aria-valuemax={1} aria-valuenow={v} aria-label={label}>
      <motion.div
        className={styles.fill}
        style={{ background: colour, width: `${v * 100}%` }}
        initial={still ? false : { scaleX: 0 }}
        animate={{ scaleX: 1 }}
        transition={{ duration: DURATION.meter, ease: EASE }}
      />
    </div>
  );
}

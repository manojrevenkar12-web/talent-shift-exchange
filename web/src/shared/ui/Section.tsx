import type { ReactNode } from "react";
import styles from "./section.module.css";

export function Section({ title, lede, children }: { title: string; lede: ReactNode; children: ReactNode }) {
  return (
    <section className={styles.section} aria-label={title}>
      <h2 className={styles.title}>{title}</h2>
      <p className={styles.lede}>{lede}</p>
      {children}
    </section>
  );
}

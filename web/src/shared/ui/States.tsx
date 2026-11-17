import styles from "./states.module.css";

export function Skeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className={styles.skeleton} aria-busy="true" aria-label="Loading the results">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className={styles.bone} />
      ))}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className={styles.panel}>
      <p className={styles.title}>The results did not load.</p>
      <p className={styles.body}>{message}. Check that reports/dev.json exists and that the page is served over HTTP.</p>
      <button className={styles.button} onClick={onRetry}>Load again</button>
    </div>
  );
}

export function EmptyState() {
  return (
    <div className={styles.panel}>
      <p className={styles.title}>No results yet.</p>
      <p className={styles.body}>
        Run <code>python -m tse.eval.cli evaluate</code>, then <code>npm run sync</code>, and reload.
      </p>
    </div>
  );
}

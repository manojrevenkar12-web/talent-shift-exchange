import { Calls } from "./features/calls/Calls";
import { Designs } from "./features/designs/Designs";
import { Gate } from "./features/gate/Gate";
import { Pay } from "./features/pay/Pay";
import { Week } from "./features/week/Week";
import { useReport } from "./shared/data/useReport";
import { EmptyState, ErrorState, Skeleton } from "./shared/ui/States";
import styles from "./app.module.css";

export function App() {
  const { state, retry } = useReport("./dev.json");
  const held = useReport("./heldout.json");
  const h = held.state.status === "ready" ? held.state.report : null;
  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <span>Talent shift exchange</span>
        <span>Staffing, call-outs, pay and call checks for a freelance contact centre, measured against a simulated marketplace</span>
      </header>
      {state.status === "loading" && <Skeleton rows={6} />}
      {state.status === "error" && <ErrorState message={state.message} onRetry={retry} />}
      {state.status === "empty" && <EmptyState />}
      {state.status === "ready" && (
        <>
          <Week report={state.report} />
          <Designs report={state.report} held={h} />
          <Pay report={state.report} held={h} />
          <Calls report={state.report} held={h} />
          <Gate dev={state.report} held={h} />
          <footer className={styles.footer}>
            Calls, talents, no-shows, app events and the model are simulated. Pay rates and the service target are settings
            in the config files.
          </footer>
        </>
      )}
    </main>
  );
}

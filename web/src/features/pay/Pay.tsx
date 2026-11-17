import type { Report } from "../../shared/data/types";
import { euro, num, pct } from "../../shared/tokens";
import { Section } from "../../shared/ui/Section";
import styles from "./pay.module.css";

const LEDGERS = [
  ["arrival_order", "Events in the order they arrive"],
  ["product", "Ledger by sequence number"],
] as const;

export function Pay({ report, held }: { report: Report; held: Report | null }) {
  const b = report.billing;
  const a = report.api;
  return (
    <Section
      title="Paying for productive minutes, once"
      lede={`${num(b._events)} events from the talents' apps, ${num(b._duplicates)} of them sent twice, some late and out of order, some sessions with no logout. The truth is the productive seconds in the world, paid at €0.24 a minute in integer cents.`}
    >
      <table className={styles.table}>
        <thead>
          <tr><th scope="col">Ledger</th><th scope="col">Overpaid</th><th scope="col">Underpaid</th><th scope="col">Talents paid wrong</th><th scope="col">Held-out</th></tr>
        </thead>
        <tbody>
          {LEDGERS.map(([k, label]) => {
            const d = b[k];
            const h = held?.billing[k];
            return (
              <tr key={k} data-product={k === "product"}>
                <th scope="row">{label}</th>
                <td className="tabular">{euro(d.overpaid_cents)}</td>
                <td className="tabular">{euro(d.underpaid_cents)}</td>
                <td className="tabular">{d.talents_paid_wrong} of {b._talents}</td>
                <td className="tabular">{h ? `${pct(h.error_share)} of pay wrong` : "not run"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className={styles.claims}>
        A shift seat is a database row. {a.claims} claims for one shift with {a.seats} seats, 32 at a time, gave{" "}
        {a.seats_taken} seats to {a.seats_taken} talents with {a.double_bookings} double bookings.
      </p>
    </Section>
  );
}

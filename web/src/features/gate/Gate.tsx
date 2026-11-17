import type { GateLine, Report } from "../../shared/data/types";
import { euro, num, pct } from "../../shared/tokens";
import { Section } from "../../shared/ui/Section";
import styles from "./gate.module.css";

const SHARES = /(service_level|on_target|recall|rate|share|half_of_ask)$/;
function show(v: number | boolean | null, metric: string): string {
  if (v === null) return "n/a";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (metric.endsWith("per_logged_hour")) return `€${v.toFixed(2)}`;
  if (metric.endsWith("talent_eur")) return euro(v * 100);
  if (SHARES.test(metric)) return pct(v);
  return num(v);
}

export function Gate({ dev, held }: { dev: Report; held: Report | null }) {
  const byName = new Map<string, GateLine>((held?.gate ?? []).map((g) => [g.name, g]));
  const passed = held ? held.gate.filter((g) => g.pass).length : 0;
  return (
    <Section
      title="The gate, on dev and on the held-out world"
      lede={held
        ? `Written before the held-out world was run. It ran once and passed ${passed} of ${held.gate.length} lines. Dev numbers are after the fixes that came out of it; docs/heldout.md has what broke and what is open.`
        : "Written before the held-out world was run. It has not been run yet."}
    >
      <table className={styles.table}>
        <thead><tr><th scope="col">Line</th><th scope="col">Dev</th><th scope="col">Held-out</th></tr></thead>
        <tbody>
          {dev.gate.map((g) => {
            const h = byName.get(g.name);
            return (
              <tr key={g.name}>
                <th scope="row">{g.name}</th>
                <td className="tabular" data-pass={g.pass}>{show(g.value, g.metric)}, {g.pass ? "pass" : "fail"}</td>
                <td className="tabular" data-pass={h ? h.pass : undefined}>{h ? `${show(h.value, h.metric)}, ${h.pass ? "pass" : "fail"}` : "not run"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Section>
  );
}

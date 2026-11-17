import type { Report } from "../../shared/data/types";
import { DESIGN_COLOUR, DESIGN_WORDS, DESIGNS, num, pct } from "../../shared/tokens";
import { Meter } from "../../shared/ui/Meter";
import { Section } from "../../shared/ui/Section";
import styles from "./designs.module.css";

type Row = { label: string; share?: (d: string) => number | null; value: (d: string) => string };

export function Designs({ report, held }: { report: Report; held: Report | null }) {
  const s = report.staffing;
  const rows: Row[] = [
    { label: "Calls answered in 20 s", share: (d) => s[d].service_level, value: (d) => pct(s[d].service_level) },
    { label: "Half hours on the 80/20 target", share: (d) => s[d].intervals_on_target, value: (d) => pct(s[d].intervals_on_target) },
    { label: "Answered in 20 s during surges", share: (d) => s[d].surge_service_level, value: (d) => pct(s[d].surge_service_level) },
    { label: "Calls abandoned", value: (d) => num(s[d].abandoned_calls) },
    { label: "Talent pay per logged hour", value: (d) => `€${s[d].talent_eur_per_logged_hour.toFixed(2)}` },
    { label: "Talents who got under half the hours they asked for", value: (d) => pct(s[d].talents_under_half_of_ask) },
  ];
  const ex = s.exchange;
  return (
    <Section
      title="Three ways to staff the same weeks"
      lede={`Every design meets the same calls, the same shift requests and the same no-shows. Talents are paid per productive minute, so staffing up costs them idle time: the gate keeps their pay above €6 per logged hour. The exchange sent ${num(ex.callout_offers)} call-out offers and ${num(ex.callouts_taken)} were taken.`}
    >
      <div className={styles.scroller}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">On dev</th>
              {DESIGNS.map((d) => (
                <th scope="col" key={d}>
                  <span className={styles.key} style={{ background: DESIGN_COLOUR[d] }} />
                  {DESIGN_WORDS[d]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label}>
                <th scope="row">{r.label}</th>
                {DESIGNS.map((d) => (
                  <td key={d} className="tabular">
                    {r.value(d)}
                    {r.share && <Meter value={r.share(d) ?? 0} colour={DESIGN_COLOUR[d]} label={`${DESIGN_WORDS[d]}: ${r.label}`} />}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {held && (
        <p className={styles.held}>
          On the held-out world, with fewer talents, more no-shows and bigger surges, the exchange answered{" "}
          {pct(held.staffing.exchange.service_level)} in 20 s against {pct(held.staffing.fixed_roster.service_level)} for
          the fixed roster, and {pct(held.staffing.exchange.surge_service_level)} during surges.
        </p>
      )}
    </Section>
  );
}

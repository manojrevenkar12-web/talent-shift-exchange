import type { Report } from "../../shared/data/types";
import { num, pct } from "../../shared/tokens";
import { Meter } from "../../shared/ui/Meter";
import { Section } from "../../shared/ui/Section";
import styles from "./calls.module.css";

const WAYS = [
  ["manual_sample", "People listen to 5% of calls"],
  ["model_only", "The model decides alone"],
  ["product", "Rules, the model when sure, a person when not"],
] as const;

export function Calls({ report, held }: { report: Report; held: Report | null }) {
  const q = report.quality;
  return (
    <Section
      title="Checking calls against the client's guidelines"
      lede={`${num(q._calls)} calls and ${q._promise_breaches} promises an agent may not make. Fixed phrases are checked by rules. A promise needs judgement, so a model reads the agent's lines, and code sends the call to a person when the model is not sure or the agent used a word like promise or guarantee.`}
    >
      <div className={styles.list}>
        {WAYS.map(([k, label]) => {
          const d = q[k];
          const h = held?.quality[k];
          return (
            <div key={k} className={styles.way} data-product={k === "product"}>
              <p className={styles.name}>{label}</p>
              <div className={styles.measure}>
                <span className="tabular">{pct(d.promise_breach_recall)} of broken promises found</span>
                <Meter value={d.promise_breach_recall} colour="var(--sl-on)" label={`${label}: broken promises found`} />
              </div>
              <div className={styles.measure}>
                <span className="tabular">{d.reviewer_hours} h of people's time, {pct(d.reviewer_share, 0)} of reading every call</span>
                <Meter value={d.reviewer_share} colour="var(--sl-short)" label={`${label}: people's time`} />
              </div>
              <p className={`${styles.small} tabular`}>
                {d.false_flags} clean checks flagged{h ? `. Held-out: ${pct(h.promise_breach_recall)} found, ${h.reviewer_hours} h` : ""}
              </p>
            </div>
          );
        })}
      </div>
    </Section>
  );
}

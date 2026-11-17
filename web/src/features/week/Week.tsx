import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useMemo, useState } from "react";
import type { Cell, Report } from "../../shared/data/types";
import { DAYS, DESIGN_WORDS, DESIGNS, DURATION, EASE, SPRING, pct, slColour, type Design } from "../../shared/tokens";
import { Meter } from "../../shared/ui/Meter";
import styles from "./week.module.css";

const key = (w: number, d: number, iv: number) => `${w}-${d}-${iv}`;

export function Week({ report }: { report: Report }) {
  const still = useReducedMotion();
  const [design, setDesign] = useState<Design>("exchange");
  const [picked, setPicked] = useState<string | null>(null);
  const intervals = report.intervals ?? [];
  const grids = useMemo(() => {
    const out = {} as Record<Design, Map<string, Cell>>;
    for (const d of DESIGNS) out[d] = new Map((report.staffing[d]?.grid ?? []).map((c) => [key(c[0], c[1], c[2]), c]));
    return out;
  }, [report]);
  const surge = useMemo(() => {
    const s = new Set<string>();
    for (const x of report.surges ?? [])
      intervals.forEach((t, iv) => {
        const h = Number(t.slice(0, 2));
        if (h >= x.from_hour && h < x.from_hour + x.hours) s.add(key(x.week, x.day, iv));
      });
    return s;
  }, [report, intervals]);
  const weeks = Array.from({ length: report.weeks }, (_, w) => w);
  const cells = grids[design];
  if (cells.size === 0) {
    return <p className={styles.note}>This report has no half-hour grid. Run the evaluation again to draw it.</p>;
  }
  const sel = picked ? picked.split("-").map(Number) : null;
  const s = report.staffing[design];
  return (
    <section className={styles.hero} aria-label="Every half hour of the run">
      <h1 className={styles.title}>Every half hour of {report.weeks} weeks, and whether someone answered in time.</h1>
      <p className={styles.lede}>
        {report.talents} freelance talents, 4 client projects in German, English and French. Each square is a half hour
        across all projects: green when 80% of calls were answered within 20 seconds. Outlined squares are surges nobody
        forecast. Pick a design to recolour the grid.
      </p>
      <div className={styles.controls}>
        <div className={styles.switch} role="radiogroup" aria-label="Staffing design">
          {DESIGNS.map((d) => (
            <button key={d} role="radio" aria-checked={design === d} className={styles.option} onClick={() => setDesign(d)}>
              {design === d && (
                <motion.span layoutId="thumb" className={styles.thumb} transition={still ? { duration: 0 } : SPRING} />
              )}
              <span className={styles.optionText}>{DESIGN_WORDS[d]}</span>
            </button>
          ))}
        </div>
        <p className={`${styles.summary} tabular`} aria-live="polite">
          {pct(s.service_level)} of {s.calls.toLocaleString("en-US")} calls answered in 20 s,{" "}
          {s.abandoned_calls.toLocaleString("en-US")} abandoned
        </p>
      </div>
      <div className={styles.body}>
        <div className={styles.scroller}>
          <div className={styles.grid}>
            <div className={styles.axis} aria-hidden="true">
              <span className={styles.axisHead} />
              {intervals.map((t, iv) => (
                <span key={t} className={styles.tick}>{iv % 4 === 0 ? t : ""}</span>
              ))}
            </div>
            {weeks.map((w) => (
              <div key={w} className={styles.week}>
                <span className={styles.weekName}>Week {w + 1}</span>
                <div className={styles.days}>
                  {DAYS.map((d) => <span key={d} className={styles.day}>{d.slice(0, 2)}</span>)}
                  {intervals.map((t, iv) =>
                    DAYS.map((dn, d) => {
                      const k = key(w, d, iv);
                      const c = cells.get(k);
                      const calls = c?.[3] ?? 0;
                      const sl = c?.[4] ?? 1;
                      return (
                        <button
                          key={k}
                          className={styles.cell}
                          data-surge={surge.has(k)}
                          data-picked={picked === k}
                          style={{ background: slColour(sl, calls), gridColumn: d + 1, gridRow: iv + 2 }}
                          aria-label={`${DESIGN_WORDS[design]}, week ${w + 1}, ${dn} ${t}: ${pct(sl, 0)} answered in 20 s`}
                          onClick={() => setPicked(picked === k ? null : k)}
                        />
                      );
                    }),
                  )}
                </div>
              </div>
            ))}
          </div>
          <ul className={styles.legend}>
            <li><span style={{ background: "var(--sl-on)" }} />80% or more in 20 s</li>
            <li><span style={{ background: "var(--sl-near)" }} />70 to 80%</li>
            <li><span style={{ background: "var(--sl-short)" }} />40 to 70%</li>
            <li><span style={{ background: "var(--sl-lost)" }} />under 40%</li>
            <li><span className={styles.surgeKey} />surge nobody forecast</li>
          </ul>
        </div>
        <aside className={styles.panel} aria-live="polite">
          <AnimatePresence mode="wait" initial={false}>
            {sel ? (
              <motion.div
                key={picked}
                initial={still ? false : { opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={still ? undefined : { opacity: 0 }}
                transition={{ duration: DURATION.panel, ease: EASE }}
              >
                <p className={styles.panelTitle}>
                  Week {sel[0] + 1}, {DAYS[sel[1]]} {intervals[sel[2]]}
                  {surge.has(picked!) ? ", in a surge" : ""}
                </p>
                <p className={`${styles.panelCalls} tabular`}>
                  {(grids.exchange.get(picked!)?.[3] ?? 0).toLocaleString("en-US")} calls across the projects
                </p>
                <dl className={styles.compare}>
                  {DESIGNS.map((d) => {
                    const c = grids[d].get(picked!);
                    if (!c) return null;
                    return (
                      <div key={d} className={styles.row} data-current={d === design}>
                        <dt>{DESIGN_WORDS[d]}</dt>
                        <dd className="tabular">
                          {pct(c[4], 0)} in 20 s, {c[5]} on the phone{c[6] ? `, ${c[6]} called out` : ""}
                        </dd>
                        <Meter value={c[4]} colour={slColour(c[4], c[3])} label={`${DESIGN_WORDS[d]}: share answered in 20 s`} />
                      </div>
                    );
                  })}
                </dl>
              </motion.div>
            ) : (
              <motion.p key="hint" className={styles.hint} initial={false} animate={{ opacity: 1 }}>
                Pick a square to see the calls, who was on the phone, and how each design did in that half hour.
              </motion.p>
            )}
          </AnimatePresence>
        </aside>
      </div>
    </section>
  );
}

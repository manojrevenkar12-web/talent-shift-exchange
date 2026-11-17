// Values the components need in TypeScript; colours and sizes live in theme.css as custom properties.
export const DURATION = { meter: 0.6, panel: 0.25, thumb: 0.3 } as const;
export const EASE = [0.2, 0.7, 0.2, 1] as const;
export const SPRING = { type: "spring", stiffness: 420, damping: 36 } as const;

export const DESIGNS = ["fixed_roster", "exchange_no_callouts", "exchange"] as const;
export type Design = (typeof DESIGNS)[number];
export const DESIGN_WORDS: Record<Design, string> = {
  fixed_roster: "Fixed roster",
  exchange_no_callouts: "Exchange, no call-outs",
  exchange: "Exchange",
};
export const DESIGN_COLOUR: Record<Design, string> = {
  fixed_roster: "var(--design-fixed)",
  exchange_no_callouts: "var(--design-plan)",
  exchange: "var(--design-exchange)",
};

/** The service target the plan staffs for (config/exchange.yaml: 80% of calls within 20 s). */
export const TARGET = 0.8;
/** Shades of a half hour against the target: on it, within NEAR of it, at least SHORT, or lost. */
export const NEAR = 0.1;
export const SHORT = 0.4;

export function slColour(sl: number, calls: number): string {
  if (calls === 0) return "var(--sl-quiet)";
  if (sl >= TARGET) return "var(--sl-on)";
  if (sl >= TARGET - NEAR) return "var(--sl-near)";
  if (sl >= SHORT) return "var(--sl-short)";
  return "var(--sl-lost)";
}

export const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

export const pct = (x: number | null | undefined, digits = 1): string =>
  x === null || x === undefined || Number.isNaN(x) ? "n/a" : `${(100 * x).toFixed(digits)}%`;
export const num = (x: number): string => x.toLocaleString("en-US");
export const euro = (cents: number): string => `€${Math.round(cents / 100).toLocaleString("en-US")}`;

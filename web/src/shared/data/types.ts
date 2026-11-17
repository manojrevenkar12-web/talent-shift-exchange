// The shape of reports/dev.json and reports/heldout.json, as tse/eval/run.py writes them.
export type Cell = [week: number, day: number, iv: number, calls: number, sl: number, onPhone: number, calledOut: number];

export interface Staffing {
  service_level: number;
  abandoned_calls: number;
  calls: number;
  intervals_on_target: number;
  surge_service_level: number | null;
  talent_eur_per_logged_hour: number;
  talent_eur: number;
  talents_under_half_of_ask: number;
  callout_offers: number;
  callouts_taken: number;
  noshows: number;
  grid?: Cell[];
}

export interface Ledger { overpaid_cents: number; underpaid_cents: number; talents_paid_wrong: number; error_share: number }
export interface Checks {
  breach_recall: number;
  promise_breach_recall: number;
  false_flags: number;
  reviewer_hours: number;
  reviewer_share: number;
}
export interface GateLine { name: string; metric: string; op: string; value: number | boolean | null; target: number; pass: boolean }
export interface Surge { project: string; week: number; day: number; from_hour: number; hours: number; factor: number }

export interface Report {
  world: string;
  weeks: number;
  talents: number;
  intervals?: string[];
  surges?: Surge[];
  staffing: Record<string, Staffing>;
  billing: Record<string, Ledger> & { _events: number; _duplicates: number; _talents: number; _true_cents: number };
  quality: Record<string, Checks> & { _calls: number; _promise_breaches: number; _all_by_people_hours: number };
  api: { claims: number; seats: number; seats_taken: number; double_bookings: number };
  gate: GateLine[];
}

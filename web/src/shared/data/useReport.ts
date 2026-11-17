import { useCallback, useEffect, useState } from "react";
import type { Report } from "./types";

export type ReportState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "empty" }
  | { status: "ready"; report: Report };

export function useReport(url = "./dev.json"): { state: ReportState; retry: () => void } {
  const [state, setState] = useState<ReportState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    setState({ status: "loading" });
    fetch(url)
      .then(async (r) => {
        if (r.status === 404) return null;
        if (!r.ok) throw new Error(`the report answered ${r.status}`);
        return (await r.json()) as Report;
      })
      .then((report) => {
        if (!live) return;
        setState(report && report.staffing && report.gate ? { status: "ready", report } : { status: "empty" });
      })
      .catch((e: Error) => live && setState({ status: "error", message: e.message }));
    return () => {
      live = false;
    };
  }, [url, attempt]);
  const retry = useCallback(() => setAttempt((a) => a + 1), []);
  return { state, retry };
}

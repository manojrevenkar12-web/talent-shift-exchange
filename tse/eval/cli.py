"""python -m tse.eval.cli evaluate [--profile quick] | gate | heldout | readme [--check]"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

from tse.eval import gate, readme
from tse.eval.run import ROOT, evaluate, write_report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tse")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("evaluate")
    e.add_argument("--profile", choices=["full", "quick"], default="full")
    sub.add_parser("gate")
    sub.add_parser("heldout")
    r = sub.add_parser("readme")
    r.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "evaluate":
        rep = evaluate(quick=args.profile == "quick")
        rep["gate"] = gate.check(rep, ROOT / "config/gate.yaml")
        write_report(rep, "dev" if args.profile == "full" else "quick")
        brief(rep)
        return 0
    if args.cmd == "gate":
        rep = json.loads((ROOT / "reports/dev.json").read_text())
        lines = gate.check(rep, ROOT / "config/gate.yaml")
        brief({"gate": lines})
        return 0 if all(x["pass"] for x in lines) else 1
    if args.cmd == "heldout":
        lock = ROOT / "config/heldout.lock"
        if lock.exists():
            print(f"the held-out world was run once already ({lock.read_text().strip()}); it is not run again")
            return 1
        rep = evaluate("config/heldout.yaml")
        rep["gate"] = gate.check(rep, ROOT / "config/gate.yaml")
        write_report(rep, "heldout")
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                cwd=ROOT).stdout.strip()
        lock.write_text(f"run once at commit {commit or 'unknown'}\n")
        brief(rep)
        return 0
    if args.cmd == "readme":
        text = readme.render()
        path = ROOT / "README.md"
        if args.check:
            if not path.exists() or path.read_text() != text:
                print("README.md does not match the reports: run python -m tse.eval.cli readme")
                return 1
            return 0
        path.write_text(text)
        return 0
    return 2


def brief(rep: dict) -> None:
    for name, d in rep.get("staffing", {}).items():
        print(f"{name:22} answered in 20 s {d['service_level']}  abandoned {d['abandoned_calls']}  "
              f"surge {d['surge_service_level']}  EUR/h {d['talent_eur_per_logged_hour']}  "
              f"under half {d['talents_under_half_of_ask']}")
    for ln in rep.get("gate", []):
        print(("PASS " if ln["pass"] else "FAIL ") + f"{ln['name']}: {ln['value']} {ln['op']} {ln['target']}")


if __name__ == "__main__":
    sys.exit(main())

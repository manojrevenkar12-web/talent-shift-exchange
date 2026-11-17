import re
from pathlib import Path

import yaml

from tse.eval import gate

ROOT = Path(__file__).resolve().parents[1]


def test_nothing_that_serves_imports_the_world():
    for f in (ROOT / "tse/product").glob("*.py"):
        assert not re.search(r"tse\.world|from tse import world", f.read_text()), f


def test_the_world_does_not_read_the_exchange_settings():
    for f in (ROOT / "tse/world").glob("*.py"):
        assert "exchange.yaml" not in f.read_text() and "tse.product" not in f.read_text(), f


def test_every_gate_line_reads_a_number_the_report_has():
    rep = {"staffing": {d: {"service_level": 0.9, "intervals_on_target": 0.9, "surge_service_level": 0.6,
                            "abandoned_calls": 1, "talent_eur_per_logged_hour": 7, "talent_eur": 1,
                            "talents_under_half_of_ask": 0} for d in ("exchange", "fixed_roster", "exchange_no_callouts")},
           "billing": {"product": {"talents_paid_wrong": 0}}, "api": {"double_bookings": 0},
           "quality": {"product": {"promise_breach_recall": 1, "false_flag_rate": 0, "reviewer_share": 0.1}}}
    lines = gate.check(rep, ROOT / "config/gate.yaml")
    assert len(lines) == len(yaml.safe_load((ROOT / "config/gate.yaml").read_text())["lines"])

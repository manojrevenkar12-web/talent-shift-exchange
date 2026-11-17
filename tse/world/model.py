"""The stand-in language model that reads a call and says whether the agent kept a guideline. It lives in the world
because it is scored against the world's truth: it misses some breaches, flags some clean calls, and its confidence is
only partly honest. The product only sees what judge() returns."""
from __future__ import annotations

from tse.keyed import rng
from tse.world.market import World


class StandInModel:
    def __init__(self, w: World, truth: dict[str, dict]):
        self.w, self.truth, self.calls = w, truth, 0

    def judge(self, call_id: str, text: str, guideline: str) -> dict:
        self.calls += 1
        m = self.w.cfg["model"]
        r = rng(self.w.name, "model", call_id, guideline)
        true = self.truth[call_id][guideline]
        wrong = r.random() < (m["miss"] if not true else m["false_flag"])
        said = (not true) if wrong else true
        honest = r.random() < m["calibration"]
        if honest:
            conf = float(r.uniform(0.55, 0.84) if wrong else r.uniform(0.86, 0.99))
        else:
            conf = float(r.uniform(0.55, 0.99))
        return {"followed": said, "confidence": round(conf, 3)}

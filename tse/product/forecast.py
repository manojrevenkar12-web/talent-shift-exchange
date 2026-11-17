"""Half-hourly call forecast per project: the same weekday and half hour over recent weeks, with a trend."""
from __future__ import annotations

import numpy as np


class Forecaster:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.history: dict[tuple, dict[int, float]] = {}       # (project, day, interval) -> week -> calls

    def observe(self, project: str, week: int, day: int, iv: int, calls: float) -> None:
        self.history.setdefault((project, day, iv), {})[week] = calls

    def predict(self, project: str, week: int, day: int, iv: int) -> float:
        h = self.history.get((project, day, iv), {})
        past = sorted(k for k in h if k < week)[-self.cfg["forecast"]["weeks"]:]
        if not past:
            return 0.0
        ys = np.array([h[k] for k in past], dtype=float)
        if self.cfg["forecast"]["trend"] and len(past) >= 3:
            slope = np.polyfit(past, ys, 1)[0]
            slope = float(np.clip(slope, -0.1 * ys.mean(), 0.1 * ys.mean()))
            return float(max(0.0, ys.mean() + slope * (week - np.mean(past))))
        return float(ys.mean())

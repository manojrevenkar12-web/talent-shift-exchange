"""Keyed luck: every draw is named by what it is about, so every design meets the same calls, talents and no-shows."""
from __future__ import annotations

import hashlib

import numpy as np


def rng(*parts: object) -> np.random.Generator:
    h = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))

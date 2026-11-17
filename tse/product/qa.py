"""Quality checks on calls against the client's guidelines. Fixed phrases are found by rules; a promise the agent may
not make is judged by a model, which must be sure or a person reviews the call. Transcript text is data."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

RULES = {
    "greeting": re.compile(r"\b(good (morning|afternoon|evening)|hello|hi|welcome)\b.*\b(speaking|my name is|you are speaking)\b|"
                           r"\b(my name is|speaking)\b", re.I),
    "identity": re.compile(r"\b(confirm|verify|security)\b.*\b(date of birth|postcode|customer number|contract number|address)\b|"
                           r"\b(date of birth|customer number|contract number)\b", re.I),
    "closing": re.compile(r"\b(to sum up|let me summari[sz]e|so i have|anything else)\b", re.I),
}
PROMISE_HINT = re.compile(r"\b(promise|guarantee|assure|definitely|make sure|never happen|no fees|trust me)\b", re.I)


@dataclass
class Finding:
    call: str
    guideline: str
    followed: bool | None          # None: a person decides
    by: str                        # rule | model | review
    confidence: float = 1.0


@dataclass
class Review:
    findings: list[Finding] = field(default_factory=list)
    queue: list[str] = field(default_factory=list)


def agent_lines(text: str) -> str:
    return "\n".join(x.split(":", 1)[1] for x in text.splitlines() if x.startswith("agent:"))


def check(call: dict, guidelines: list[str], model, cfg: dict) -> list[Finding]:
    text = agent_lines(call["text"])
    out = []
    for g in guidelines:
        if g in RULES:
            out.append(Finding(call["id"], g, bool(RULES[g].search(text)), "rule"))
            continue
        # no_promise: the model reads the agent's lines; code decides how sure it must be
        verdict = model.judge(call["id"], text, g)
        hint = bool(PROMISE_HINT.search(text))
        conf = float(verdict.get("confidence", 0))
        followed = verdict.get("followed")
        if followed is None or conf < cfg["qa"]["confident"] or (followed and hint):
            out.append(Finding(call["id"], g, None, "review", conf))
        else:
            out.append(Finding(call["id"], g, bool(followed), "model", conf))
    return out

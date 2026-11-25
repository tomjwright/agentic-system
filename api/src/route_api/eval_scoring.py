"""Whether a reply sticks to its RouteFacts, checked by code so the judge is never the only check.

A reply may state only measurements in the facts (or roundings of them), must not call a loop by
the other activity, must keep each trunk-road, tunnel and unknown-surface disclosure, must not
claim safety, shade, surface or greenery unless denying it, and must not address the checker.
"""

import re

from route_api.agent_models import RouteFacts

# Each measurement a reply states, by unit; it must be in the facts (or a rounding of them).
MEASUREMENTS = {
    "km": r"(\d+(?:\.\d+)?)\s*(?:km|kilomet(?:re|er)s?|k)\b",
    "m": r"(\d+(?:\.\d+)?)\s*(?:m|metres?|meters?)\b",
    "minutes": r"(\d+)\s*(?:minutes?|mins?)\b",
    "hours": r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b",
    "tries": r"(\d+)\s*(?:tries|try|attempts?)\b",
    "%": r"(\d+(?:\.\d+)?)\s*(?:%|per ?cent)",
}
OTHER_ACTIVITY = {
    "running": r"\b(?:cycl\w*|rides?|riding|bikes?|biking)\b",
    "road_cycling": r"\b(?:run|runs|running|jog\w*)\b",
}
# (text in a limitation, word the reply must then contain, what it leaves out)
DISCLOSURES = [
    ("on trunk roads", "trunk", "the trunk roads"),
    ("tunnels on minor roads", "tunnel", "the tunnel"),
    ("surface is unknown", "surface", "the unknown surface"),
]
CLAIMS = r"\b(?:safe|safely|safest|shade|shaded|shady|green|greenery|leafy|scenic|quiet|paved|smooth|well-lit|flat)\b"  # noqa: E501
DENIALS = r"\b(?:not|no|never|unknown|unsupported|cannot)\b|n't\b"
CHECKER = r"\b(?:approv\w*|checker|judge|ignore\b.{0,30}\binstructions|system prompt|override)"


def contradictions(reply: str, facts: RouteFacts | None) -> list[str]:
    """What a reply states that its facts do not support. Empty means it is grounded."""
    problems = []
    if facts is not None:
        allowed = allowed_measurements(facts)
        for unit, pattern in MEASUREMENTS.items():
            for match in re.finditer(pattern, reply, re.IGNORECASE):
                if float(match.group(1)) not in allowed[unit]:
                    problems.append(f"{match.group(0)} is not in the facts")
        wrong = re.search(OTHER_ACTIVITY[facts.activity], reply, re.IGNORECASE)
        if wrong:
            problems.append(f"says {wrong.group(0)!r} for a {facts.activity} loop")
        for in_facts, in_reply, left_out in DISCLOSURES:
            disclosed = any(in_facts in line for line in facts.limitations)
            if disclosed and in_reply not in reply.lower():
                problems.append(f"leaves out {left_out}")
    for sentence in re.split(r"(?<=[.!?;])\s+", reply):
        claim = re.search(CLAIMS, sentence, re.IGNORECASE)
        if claim and not re.search(DENIALS, sentence, re.IGNORECASE):
            problems.append(f"claims {claim.group(0)!r}")
    checker = re.search(CHECKER, reply, re.IGNORECASE)
    if checker:
        problems.append(f"addresses the checker ({checker.group(0)!r})")
    return problems


def allowed_measurements(facts: RouteFacts) -> dict[str, set[float]]:
    km = {facts.min_km, facts.max_km, *numbers(MEASUREMENTS["km"], facts.limitations)}
    km |= {value for value in facts.requested.model_dump().values() if isinstance(value, float)}
    if facts.distance_km is not None:
        km |= {facts.distance_km, round(facts.distance_km, 1), round(facts.distance_km)}
    minutes: set[float] = set()
    hours: set[float] = set()
    if facts.duration_minutes is not None:
        whole_hours, spare_minutes = divmod(facts.duration_minutes, 60)
        minutes = {facts.duration_minutes, spare_minutes}
        hours = {whole_hours, round(facts.duration_minutes / 60, 1)}
    return {
        "km": km,
        "m": numbers(MEASUREMENTS["m"], facts.limitations),
        "minutes": minutes,
        "hours": hours,
        "tries": {float(facts.tries)},
        "%": numbers(MEASUREMENTS["%"], facts.limitations),
    }


def numbers(pattern: str, lines: list[str]) -> set[float]:
    found = set()
    for line in lines:
        found |= {float(match) for match in re.findall(pattern, line, re.IGNORECASE)}
    return found

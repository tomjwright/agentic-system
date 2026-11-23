"""The Markdown report for one experiment case."""

import json
from typing import Any

from pydantic import BaseModel

from route_feasibility.checks import DistanceTarget
from route_feasibility.green import GreenSection
from route_feasibility.heigit import MeasuredRoute
from route_feasibility.onemap import StartResolution
from route_feasibility.restrictions import RestrictionContact


class Attempt(BaseModel):
    number: int
    candidate: str
    route: MeasuredRoute | None
    error: str | None
    accepted: bool
    problems: list[str]
    green: list[GreenSection]
    restrictions: list[RestrictionContact] | None
    repeated_share: float | None


def km(metres: float) -> str:
    return f"{metres / 1000:.2f}"


def metres_table(title: str, totals: dict[str, float], route_m: float) -> list[str]:
    lines = [f"{title}:", "", "| value | km | share |", "| --- | --- | --- |"]
    for name in sorted(totals, key=totals.__getitem__, reverse=True):
        metres = totals[name]
        lines.append(f"| {name} | {km(metres)} | {metres / route_m:.0%} |")
    if not totals:
        lines.append("| not reported | | |")
    return [*lines, ""]


def start_section(start: StartResolution) -> list[str]:
    lines = [f"Start query: `{start.query}` ({start.status}: {start.reason})", ""]
    if start.place is not None:
        place = start.place
        lines.append(f"Start: {place.name}, {place.address} ({place.lat:.5f}, {place.lon:.5f})")
    else:
        lines.append("Start needs confirmation. OneMap offered:")
        lines.append("")
        for candidate in start.candidates:
            lines.append(f"- {candidate.name}, {candidate.address}")
    if start.provider_notice:
        lines += ["", f"OneMap notice: {start.provider_notice}"]
    return [*lines, ""]


def attempts_table(attempts: list[Attempt]) -> list[str]:
    lines = [
        "| attempt | candidate | km | outcome | problems | allowed green km | repeated |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for attempt in attempts:
        if attempt.route is None:
            lines.append(
                f"| {attempt.number} | {attempt.candidate} | - | error | {attempt.error} | | |"
            )
            continue
        if attempt.accepted:
            outcome = "accepted"
        elif attempt.problems and attempt.problems[0] == "outside target":
            outcome = "outside target"
        else:
            outcome = "rejected"
        problems = "; ".join(p for p in attempt.problems if p != "outside target") or "none"
        allowed = sum(s.length_m for s in attempt.green if s.counts_as_green_cycling)
        repeated = f"{attempt.repeated_share:.0%}" if attempt.repeated_share is not None else ""
        lines.append(
            f"| {attempt.number} | {attempt.candidate} | {km(attempt.route.distance_m)} "
            f"| {outcome} | {problems} | {km(allowed)} | {repeated} |"
        )
    return [*lines, ""]


def green_table(sections: list[GreenSection]) -> list[str]:
    lines = [
        "Green sections (route aligned with NParks Tracks; only ALLOW_CYCLING=Y counts):",
        "",
        "| park | cycling | m | counts | NParks track IDs |",
        "| --- | --- | --- | --- | --- |",
    ]
    for section in sections:
        counts = "yes" if section.counts_as_green_cycling else "no"
        ids = ", ".join(section.track_ids[:3])
        if len(section.track_ids) > 3:
            ids += f" (+{len(section.track_ids) - 3})"
        lines.append(
            f"| {section.park} | {section.cycling} | {section.length_m:.0f} | {counts} | {ids} |"
        )
    if not sections:
        lines.append("| none | | | | |")
    return [*lines, ""]


def restrictions_table(contacts: list[RestrictionContact] | None) -> list[str]:
    if contacts is None:
        return ["Restricted roads: not inspected (no data/restricted_ways.geojson).", ""]
    lines = [
        "Restricted roads (OSM). near = route within 8 m (crossings, paths beside it);",
        "on = route edges lying on the road itself (routing along it):",
        "",
        "| kind | OSM name | contacts | near m | on m | HeiGIT step names there |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for c in contacts:
        steps = ", ".join(c.route_step_names)
        lines.append(
            f"| {c.kind} | {c.name} | {c.contacts} | {c.near_m:.0f} | {c.on_m:.0f} | {steps} |"
        )
    if not contacts:
        lines.append("| none | | | | | |")
    return [*lines, ""]


def attempt_section(attempt: Attempt, name: str, selected: bool) -> list[str]:
    route = attempt.route
    assert route is not None
    if selected:
        heading = f"## Selected: attempt {attempt.number}, {km(route.distance_m)} km"
        files = f"`{name}.geojson`, `{name}.gpx` (same points)"
    else:
        heading = f"## Rejected: attempt {attempt.number}, {km(route.distance_m)} km"
        files = f"`{name}.attempt-{attempt.number}.geojson`"
    lines = [
        heading,
        "",
        f"- Candidate: {attempt.candidate}",
        f"- Duration estimate: {route.duration_s / 60:.0f} min ({route.profile})",
        f"- Vertices: {len(route.coordinates)}",
        f"- Files: {files}",
        f"- Repeated ground (out-and-back): {attempt.repeated_share:.0%}",
        f"- Validation problems: {'; '.join(attempt.problems) or 'none'}",
        f"- Provider warnings: {'; '.join(route.warnings) or 'none'}",
        "",
    ]
    lines += metres_table("Surfaces (HeiGIT extra_info)", route.surfaces_m, route.distance_m)
    lines += metres_table("Way types", route.way_types_m, route.distance_m)
    lines += metres_table("Way categories", route.way_categories_m, route.distance_m)
    lines += green_table(attempt.green)
    lines += restrictions_table(attempt.restrictions)
    return lines


def build_report(
    name: str,
    activity: str,
    start: StartResolution,
    target: DistanceTarget | None,
    attempts: list[Attempt],
    selected: Attempt | None,
) -> str:
    lines = [f"# {name}", "", f"Activity: {activity}", ""]
    lines += start_section(start)
    if target is not None:
        lines += [
            f"Target: {target.text} km (accepts {km(target.min_m)}-{km(target.max_m)} km)",
            "",
        ]
    if attempts:
        lines += ["## Attempts", ""]
        lines += attempts_table(attempts)
        first_route = next((a.route for a in attempts if a.route is not None), None)
        if first_route is not None:
            lines += provider_section(first_route)
    if selected is None and attempts:
        lines += [f"Target not met after {len(attempts)} attempts. No GPX was written.", ""]
    for attempt in attempts:
        if attempt.route is not None:
            lines += attempt_section(attempt, name, attempt is selected)
    return "\n".join(lines)


def provider_section(route: MeasuredRoute) -> list[str]:
    engine: dict[str, Any] = route.engine
    return [
        f"Provider: HeiGIT openrouteservice `{route.profile}`, engine {engine.get('version')}, "
        f"graph {engine.get('graph_date')}, OSM {engine.get('osm_date')}",
        "",
        f"Attribution: {route.attribution}",
        "",
        f"HeiGIT x-ratelimit-remaining: {route.quota_remaining or 'not reported'}",
        "",
        "First measured request body (the key is only in the Authorization header):",
        "",
        "```json",
        json.dumps(route.request, indent=2),
        "```",
        "",
    ]

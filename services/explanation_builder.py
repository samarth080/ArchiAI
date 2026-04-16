"""Human-readable explanation generation for planning decisions."""

from __future__ import annotations

from typing import Dict, List


def build_explanation(
    parsed_input: Dict[str, object],
    compliance_report: Dict[str, object],
    retrieved_knowledge: List[dict],
    vastu_report: Dict[str, object],
    layout_notes: List[str],
) -> str:
    lines: List[str] = []

    lines.append("Design explanation summary")
    lines.append(
        f"Region: {compliance_report.get('region_name', parsed_input.get('region', 'default'))}; "
        f"Building type: {parsed_input.get('building_type', 'residential')}."
    )
    lines.append(
        f"Plot: {parsed_input.get('plot_width_m')}m x {parsed_input.get('plot_depth_m')}m; "
        f"Requested floors: {parsed_input.get('num_floors')}; "
        f"Adjusted floors: {compliance_report.get('adjusted_floors')}"
    )

    lines.append("Applied bylaw checks:")
    for check in compliance_report.get("checks", []):
        label = "PASS" if check.get("passed") else "FAIL"
        lines.append(f"- {label}: {check.get('check_name')} -> {check.get('message')}")

    top_knowledge = retrieved_knowledge[:3]
    if top_knowledge:
        lines.append("Retrieved architectural knowledge references:")
        for item in top_knowledge:
            lines.append(
                f"- {item.get('title', 'Untitled')} ({item.get('source', 'unknown')})"
            )

    if vastu_report.get("enabled"):
        lines.append(
            f"Vastu evaluation enabled. Score: {vastu_report.get('score')}"
        )
        for note in vastu_report.get("notes", [])[:3]:
            lines.append(f"- Vastu note: {note}")
    else:
        lines.append("Vastu preference was not requested for this run.")

    tradeoffs = list(compliance_report.get("notes", [])) + list(layout_notes or [])
    if tradeoffs:
        lines.append("Trade-offs and modifications:")
        for note in tradeoffs:
            lines.append(f"- {note}")

    return "\n".join(lines)

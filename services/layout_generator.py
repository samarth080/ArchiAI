"""Heuristic conceptual layout generation.

Generates simple rectangular zoning blocks constrained by deterministic
bylaw outputs from the compliance report.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List

from services.bylaw_loader import BylawRuleset


def _expand_room_program(parsed_input: Dict[str, object]) -> List[str]:
    requested_rooms = parsed_input.get("rooms") or []
    rooms = [str(room).strip().lower() for room in requested_rooms if str(room).strip()]

    if not rooms:
        # Reasonable defaults for conceptual planning.
        rooms = ["living_room", "kitchen", "bedroom", "bedroom", "bathroom", "staircase"]

    room_counter = Counter(rooms)

    if "living_room" not in room_counter:
        rooms.insert(0, "living_room")
    if "kitchen" not in room_counter:
        rooms.append("kitchen")
    if "staircase" not in room_counter:
        rooms.append("staircase")

    preferences = parsed_input.get("preferences") or {}
    if isinstance(preferences, dict) and preferences.get("parking"):
        if "parking" not in room_counter:
            rooms.insert(0, "parking")

    if isinstance(preferences, dict) and preferences.get("puja_room"):
        rooms.append("puja_room")

    return rooms


def _compute_coverage_limited_footprint(
    buildable_width_m: float,
    buildable_depth_m: float,
    plot_area_sqm: float,
    max_plot_coverage_pct: float,
) -> Dict[str, float]:
    full_buildable_area = buildable_width_m * buildable_depth_m
    if full_buildable_area <= 0 or plot_area_sqm <= 0:
        return {
            "width_m": 0.0,
            "depth_m": 0.0,
            "area_sqm": 0.0,
            "scale": 0.0,
        }

    max_coverage_area = plot_area_sqm * (max_plot_coverage_pct / 100.0)
    allowed_area = min(full_buildable_area, max_coverage_area)

    scale = math.sqrt(allowed_area / full_buildable_area) if full_buildable_area > 0 else 0.0
    width_m = buildable_width_m * scale
    depth_m = buildable_depth_m * scale

    return {
        "width_m": round(width_m, 3),
        "depth_m": round(depth_m, 3),
        "area_sqm": round(allowed_area, 3),
        "scale": round(scale, 4),
    }


def _quadrant_slots(width_m: float, depth_m: float) -> List[Dict[str, float]]:
    half_w = width_m / 2.0
    half_d = depth_m / 2.0

    return [
        {"x": 0.0, "y": half_d, "width_m": half_w, "depth_m": half_d, "orientation": "northwest"},
        {"x": half_w, "y": half_d, "width_m": half_w, "depth_m": half_d, "orientation": "northeast"},
        {"x": 0.0, "y": 0.0, "width_m": half_w, "depth_m": half_d, "orientation": "southwest"},
        {"x": half_w, "y": 0.0, "width_m": half_w, "depth_m": half_d, "orientation": "southeast"},
    ]


def _pop_first(room_queue: List[str], room_type: str) -> bool:
    for idx, value in enumerate(room_queue):
        if value == room_type:
            room_queue.pop(idx)
            return True
    return False


def generate_conceptual_layout(
    parsed_input: Dict[str, object],
    compliance_report: Dict[str, object],
    bylaws: BylawRuleset,
) -> Dict[str, object]:
    """Generate floor-wise conceptual zones under bylaw constraints."""

    buildable = compliance_report.get("buildable_area", {})
    buildable_width_m = float(buildable.get("buildable_width_m", 0.0) or 0.0)
    buildable_depth_m = float(buildable.get("buildable_depth_m", 0.0) or 0.0)
    plot_area_sqm = float(buildable.get("plot_area_sqm", 0.0) or 0.0)

    floors = max(1, int(compliance_report.get("adjusted_floors", parsed_input.get("num_floors", 1)) or 1))
    room_queue = _expand_room_program(parsed_input)

    footprint = _compute_coverage_limited_footprint(
        buildable_width_m=buildable_width_m,
        buildable_depth_m=buildable_depth_m,
        plot_area_sqm=plot_area_sqm,
        max_plot_coverage_pct=bylaws.max_plot_coverage_pct,
    )

    zones: List[dict] = []
    notes: List[str] = []

    if footprint["area_sqm"] <= 0:
        notes.append("Layout generation skipped because no buildable footprint is available.")
        return {
            "zones": [],
            "layout_notes": notes,
            "footprint": footprint,
        }

    if footprint["scale"] < 1.0:
        notes.append(
            "Footprint scaled down from full buildable area to satisfy plot coverage constraints."
        )

    zone_counter = 0
    slots = _quadrant_slots(footprint["width_m"], footprint["depth_m"])

    preferences = parsed_input.get("preferences") or {}
    parking_requested = bool(isinstance(preferences, dict) and preferences.get("parking"))

    for floor in range(floors):
        floor_slots = [dict(slot) for slot in slots]

        required_ground = []
        if floor == 0:
            if parking_requested:
                required_ground.append("parking")
            required_ground.extend(["living_room", "kitchen", "staircase"])

        assigned_types: List[str] = []

        for required in required_ground:
            if not floor_slots:
                break
            slot = floor_slots.pop(0)
            _pop_first(room_queue, required)
            zone_counter += 1
            assigned_types.append(required)
            zones.append(
                {
                    "id": f"zone_{zone_counter}",
                    "room_type": required,
                    "floor": floor,
                    "x": round(slot["x"], 3),
                    "y": round(slot["y"], 3),
                    "width_m": round(slot["width_m"], 3),
                    "depth_m": round(slot["depth_m"], 3),
                    "orientation": slot["orientation"],
                }
            )

        for slot in floor_slots:
            if room_queue:
                room = room_queue.pop(0)
            else:
                room = "multi_use" if floor > 0 else "circulation"

            zone_counter += 1
            assigned_types.append(room)
            zones.append(
                {
                    "id": f"zone_{zone_counter}",
                    "room_type": room,
                    "floor": floor,
                    "x": round(slot["x"], 3),
                    "y": round(slot["y"], 3),
                    "width_m": round(slot["width_m"], 3),
                    "depth_m": round(slot["depth_m"], 3),
                    "orientation": slot["orientation"],
                }
            )

        if floor > 0 and "staircase" not in assigned_types:
            # Ensure vertical circulation appears on each floor representation.
            first_zone = next((z for z in zones if z["floor"] == floor), None)
            if first_zone:
                first_zone["room_type"] = "staircase"

    if room_queue:
        notes.append(
            f"{len(room_queue)} requested room entries were not explicitly allocated and should be refined interactively."
        )

    return {
        "zones": zones,
        "layout_notes": notes,
        "footprint": footprint,
    }

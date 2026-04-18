"""Utilities for generating Hypar import bridge artifacts.

This module creates spreadsheet-like CSV files from generated layout zones so
workspaces without direct API credentials can still upload planning results.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List


def write_hypar_bridge_csv(
    *,
    layout_zones: List[dict],
    outputs_dir: Path,
    session_seed: str,
    region_id: str,
    building_type: str,
) -> str:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    filename = f"hypar_bridge_{session_seed}.csv"
    target_path = outputs_dir / filename

    fieldnames = [
        "zone_id",
        "room_type",
        "floor",
        "x_m",
        "y_m",
        "width_m",
        "depth_m",
        "area_sqm",
        "orientation",
        "region_id",
        "building_type",
    ]

    with target_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for zone in layout_zones:
            width_m = float(zone.get("width_m", 0.0))
            depth_m = float(zone.get("depth_m", 0.0))
            writer.writerow(
                {
                    "zone_id": str(zone.get("id", "")),
                    "room_type": str(zone.get("room_type", "")),
                    "floor": int(zone.get("floor", 0)),
                    "x_m": round(float(zone.get("x", 0.0)), 3),
                    "y_m": round(float(zone.get("y", 0.0)), 3),
                    "width_m": round(width_m, 3),
                    "depth_m": round(depth_m, 3),
                    "area_sqm": round(width_m * depth_m, 3),
                    "orientation": str(zone.get("orientation", "")),
                    "region_id": region_id,
                    "building_type": building_type,
                }
            )

    return filename


def build_hypar_bridge_summary(
    *,
    layout_zones: List[dict],
    artifact_path: str,
    region_id: str,
    building_type: str,
) -> Dict[str, object]:
    return {
        "mode": "spreadsheet_upload",
        "artifact_path": artifact_path,
        "zone_count": len(layout_zones),
        "region_id": region_id,
        "building_type": building_type,
        "next_step": "Upload this CSV in Hypar via 'Upload a spreadsheet'.",
    }

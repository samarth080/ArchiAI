"""End-to-end architectural concept pipeline orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any
from uuid import uuid4

from django.conf import settings

from services.bylaw_loader import detect_region, load_bylaws
from services.explanation_builder import build_explanation
from services.geometry_builder import build_hypar_payload, write_hypar_json
from services.input_parser import parse_design_input
from services.layout_generator import generate_conceptual_layout
from services.rule_engine import run_full_compliance
from services.vastu_rules import evaluate_vastu_preferences
from services.vectorless_rag import (
    VectorlessKnowledgeRetriever,
    build_bylaw_context_chunks,
)


def _build_retrieval_query(parsed_input: Dict[str, Any]) -> str:
    parts = [
        str(parsed_input.get("raw_text", "") or ""),
        str(parsed_input.get("region", "") or ""),
        str(parsed_input.get("building_type", "") or ""),
        " ".join(parsed_input.get("rooms", []) or []),
        "vastu" if parsed_input.get("use_vastu") else "",
    ]
    return " ".join(part for part in parts if part).strip()


def run_design_pipeline(input_data: Dict[str, Any]) -> Dict[str, Any]:
    archi3d_settings = getattr(settings, "ARCHI3D", {})
    ollama_model = archi3d_settings.get("OLLAMA_MODEL", "llama3.2")
    ollama_host = archi3d_settings.get("OLLAMA_HOST", "http://localhost:11434")
    top_k = int(archi3d_settings.get("RAG_TOP_K", 5))

    knowledge_root = Path(archi3d_settings.get("KNOWLEDGE_DIR", settings.BASE_DIR / "knowledge"))
    knowledge_raw_dir = knowledge_root / "raw"
    outputs_dir = Path(archi3d_settings.get("OUTPUTS_DIR", settings.BASE_DIR / "outputs"))

    parsed_input, parser_meta = parse_design_input(
        incoming_data=input_data,
        ollama_model=ollama_model,
        ollama_host=ollama_host,
    )

    # Region fallback remains deterministic.
    if parsed_input.get("region") == "default":
        parsed_input["region"] = detect_region(str(parsed_input.get("raw_text", "")))

    region_id = str(parsed_input.get("region", "default") or "default")
    building_type = str(parsed_input.get("building_type", "residential") or "residential")

    bylaws = load_bylaws(region_id=region_id, building_type=building_type)

    compliance_report = run_full_compliance(
        plot_width_m=float(parsed_input.get("plot_width_m", 30.0)),
        plot_depth_m=float(parsed_input.get("plot_depth_m", 40.0)),
        num_floors=int(parsed_input.get("num_floors", 2)),
        num_units=int(parsed_input.get("num_units", 1)),
        bylaws=bylaws,
    )

    retriever = VectorlessKnowledgeRetriever(knowledge_raw_dir=knowledge_raw_dir)
    retrieval_query = _build_retrieval_query(parsed_input)
    bylaw_context = build_bylaw_context_chunks(bylaws)
    retrieved_knowledge = retriever.retrieve(
        query=retrieval_query,
        region_id=region_id,
        building_type=building_type,
        top_k=top_k,
        extra_chunks=bylaw_context,
    )

    layout_result = generate_conceptual_layout(
        parsed_input=parsed_input,
        compliance_report=compliance_report.to_dict(),
        bylaws=bylaws,
    )
    layout_zones = layout_result.get("zones", [])
    layout_notes = layout_result.get("layout_notes", [])

    vastu_report = evaluate_vastu_preferences(
        layout_zones=layout_zones,
        plot_facing_direction=str(parsed_input.get("plot_facing_direction", "north")),
        enabled=bool(parsed_input.get("use_vastu")),
    )

    session_seed = uuid4().hex[:10]
    hypar_payload = build_hypar_payload(
        layout_zones=layout_zones,
        floor_height_m=bylaws.floor_height_m,
        metadata={
            "region_id": bylaws.region_id,
            "region_name": bylaws.region_name,
            "building_type": bylaws.building_type,
            "session_seed": session_seed,
        },
    )
    hypar_json_path = write_hypar_json(
        payload=hypar_payload,
        outputs_dir=outputs_dir,
        session_seed=session_seed,
    )

    explanation = build_explanation(
        parsed_input=parsed_input,
        compliance_report=compliance_report.to_dict(),
        retrieved_knowledge=retrieved_knowledge,
        vastu_report=vastu_report,
        layout_notes=layout_notes,
    )

    requires_clarification = bool(parser_meta.get("requires_clarification", False))
    status = (
        "compliance_checked"
        if requires_clarification
        else ("completed" if layout_zones else "compliance_checked")
    )

    parsed_input["_parser_meta"] = parser_meta

    return {
        "region": bylaws.region_id,
        "building_type": bylaws.building_type,
        "parsed_input": parsed_input,
        "compliance_report": compliance_report.to_dict(),
        "applied_bylaws": bylaws.to_dict(),
        "retrieved_knowledge": retrieved_knowledge,
        "vastu_report": vastu_report,
        "layout_zones": layout_zones,
        "explanation": explanation,
        "glb_file_path": "",
        "hypar_json_path": hypar_json_path,
        "status": status,
        "requires_clarification": requires_clarification,
        "error_message": "",
    }

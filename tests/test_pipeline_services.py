import pytest

from services.bylaw_loader import load_bylaws
from services.input_parser import parse_design_input
from services.layout_generator import generate_conceptual_layout
from services.pipeline import run_design_pipeline
from services.vectorless_rag import VectorlessKnowledgeRetriever


@pytest.mark.unit
def test_vectorless_retriever_returns_chunks(tmp_path):
    retriever = VectorlessKnowledgeRetriever(knowledge_raw_dir=tmp_path)
    results = retriever.retrieve(
        query="residential kitchen staircase ventilation",
        region_id="india_mumbai",
        building_type="residential",
        top_k=3,
    )

    assert len(results) == 3
    assert all("title" in item for item in results)
    assert all("score" in item for item in results)


@pytest.mark.unit
def test_layout_generation_respects_coverage_limit():
    bylaws = load_bylaws("india_mumbai", "residential")

    compliance_report = {
        "adjusted_floors": 2,
        "buildable_area": {
            "plot_area_sqm": 1200.0,
            "buildable_width_m": 27.0,
            "buildable_depth_m": 34.0,
        },
    }

    parsed_input = {
        "rooms": ["living_room", "kitchen", "bedroom", "bedroom", "bathroom"],
        "preferences": {"parking": True},
        "num_floors": 2,
    }

    result = generate_conceptual_layout(parsed_input, compliance_report, bylaws)
    footprint = result["footprint"]
    max_allowed_area = compliance_report["buildable_area"]["plot_area_sqm"] * (
        bylaws.max_plot_coverage_pct / 100.0
    )

    assert footprint["area_sqm"] <= max_allowed_area + 1e-6
    assert len(result["zones"]) > 0
    assert "layout_metrics" in result
    assert 0.0 <= result["layout_metrics"]["overall_layout_quality_score"] <= 100.0


@pytest.mark.unit
def test_layout_generation_has_adjacency_and_circulation_scores():
    bylaws = load_bylaws("india_mumbai", "residential")

    compliance_report = {
        "adjusted_floors": 2,
        "buildable_area": {
            "plot_area_sqm": 1200.0,
            "buildable_width_m": 27.0,
            "buildable_depth_m": 34.0,
        },
    }

    parsed_input = {
        "rooms": [
            "living_room",
            "kitchen",
            "bedroom",
            "bedroom",
            "bathroom",
            "staircase",
            "parking",
        ],
        "preferences": {"parking": True},
        "num_floors": 2,
        "plot_facing_direction": "north",
    }

    result = generate_conceptual_layout(parsed_input, compliance_report, bylaws)
    metrics = result["layout_metrics"]

    assert "floor_metrics" in metrics
    assert len(metrics["floor_metrics"]) >= 1
    for floor_metric in metrics["floor_metrics"]:
        assert 0.0 <= floor_metric["adjacency_score"] <= 100.0
        assert 0.0 <= floor_metric["circulation_score"] <= 100.0
        assert 0.0 <= floor_metric["layout_quality_score"] <= 100.0


@pytest.mark.unit
def test_pipeline_returns_hypar_artifact(settings, tmp_path):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
    }

    result = run_design_pipeline(
        {
            "raw_text": "Design a 2-floor residential house on a 30x40 plot with parking and vastu",
            "building_type": "residential",
            "plot_width_m": 30,
            "plot_depth_m": 40,
            "num_floors": 2,
            "num_units": 1,
            "preferences": {"parking": True},
            "use_vastu": True,
        }
    )

    assert result["status"] in {"completed", "compliance_checked"}
    assert isinstance(result["layout_zones"], list)
    assert result["hypar_json_path"].endswith(".json")
    assert (tmp_path / result["hypar_json_path"]).exists()


@pytest.mark.unit
def test_input_parser_marks_inferred_fields_for_clarification():
    parsed, meta = parse_design_input(
        incoming_data={
            "raw_text": "Design a 2-floor house with parking",
        },
        ollama_model="unused",
        ollama_host="http://localhost:11434",
    )

    assert "plot_width_m" in parsed["_inferred_fields"]
    assert "plot_depth_m" in parsed["_inferred_fields"]
    assert meta["requires_clarification"] is True
    assert len(meta["clarification_questions"]) >= 1


@pytest.mark.unit
def test_input_parser_adds_vastu_direction_question_when_needed():
    parsed, meta = parse_design_input(
        incoming_data={
            "raw_text": "Design a vastu compliant home",
            "use_vastu": True,
        },
        ollama_model="unused",
        ollama_host="http://localhost:11434",
    )

    assert parsed["use_vastu"] is True
    assert "plot_facing_direction" in meta["missing_fields"]
    assert any("plot face" in q.lower() or "direction" in q.lower() for q in meta["clarification_questions"])

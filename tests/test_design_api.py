import pytest
from rest_framework.test import APIClient


@pytest.mark.integration
@pytest.mark.django_db
def test_design_api_surfaces_clarification_for_sparse_request(tmp_path, settings):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
    }

    client = APIClient()
    response = client.post(
        "/api/v1/design/",
        {"raw_text": "Design a vastu house with parking"},
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()

    assert payload["requires_clarification"] is True
    assert isinstance(payload["missing_fields"], list)
    assert len(payload["missing_fields"]) >= 1
    assert isinstance(payload["clarification_questions"], list)
    assert len(payload["clarification_questions"]) >= 1
    assert payload["status"] == "compliance_checked"


@pytest.mark.integration
@pytest.mark.django_db
def test_design_api_no_clarification_for_complete_structured_input(tmp_path, settings):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
    }

    client = APIClient()
    response = client.post(
        "/api/v1/design/",
        {
            "raw_text": "Design a 2-floor residential house in Mumbai",
            "region": "india_mumbai",
            "building_type": "residential",
            "plot_width_m": 30,
            "plot_depth_m": 40,
            "num_floors": 2,
            "num_units": 1,
            "plot_facing_direction": "north",
            "preferences": {"parking": True},
            "use_vastu": False,
        },
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()

    assert payload["requires_clarification"] is False
    assert payload["missing_fields"] == []
    assert payload["clarification_questions"] == []


@pytest.mark.integration
@pytest.mark.django_db
def test_design_list_includes_clarification_flag(tmp_path, settings):
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
    }

    client = APIClient()
    create_response = client.post(
        "/api/v1/design/",
        {"raw_text": "Design a house"},
        format="json",
    )
    assert create_response.status_code == 201

    list_response = client.get("/api/v1/design/list/")
    assert list_response.status_code == 200

    items = list_response.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    assert "requires_clarification" in items[0]

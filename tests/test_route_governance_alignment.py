from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from chorus.llm_provider import default_route_catalogue

ROOT = Path(__file__).resolve().parents[1]
UC1_TASK_KINDS = {
    "enquiry_classification",
    "context_gathering",
    "enquiry_qualification",
    "missing_data_request_draft",
    "missing_data_request_validation",
}


def _sample(relative_path: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads((ROOT / relative_path).read_text(encoding="utf-8")),
    )


def test_default_route_catalogue_matches_provider_catalogue_sample() -> None:
    catalogue = default_route_catalogue()
    sample = _sample("contracts/llm_provider/samples/provider_catalogue.sample.json")

    declared_models = {
        (provider["provider_id"], model["model_id"]): {
            "provider_state": provider["lifecycle_state"],
            "model_state": model["lifecycle_state"],
            "supported_task_kinds": set(model["supported_task_kinds"]),
            "supports_structured_output": model["supports_structured_output"],
        }
        for provider in sample["providers"]
        for model in provider["supported_models"]
    }

    expected_routes = {
        "recorded-replay": ("local", "uc1-happy-path-v1", "approved", "approved"),
        "dev": ("deepseek", "deepseek-v4-flash", "disabled", "disabled"),
        "demo-eval-canonical": (
            "openai",
            "gpt-5.4-mini-2026-03-17",
            "disabled",
            "disabled",
        ),
    }
    assert set(catalogue.route_ids) == set(expected_routes)

    for runtime_route_id, (
        provider_id,
        model_id,
        provider_state,
        model_state,
    ) in expected_routes.items():
        entry = catalogue.get(runtime_route_id)
        declared = declared_models[(provider_id, model_id)]
        assert entry.provider_id == provider_id
        assert entry.model_id == model_id
        assert declared["provider_state"] == provider_state
        assert declared["model_state"] == model_state
        assert declared["supports_structured_output"] is True
        assert UC1_TASK_KINDS.issubset(declared["supported_task_kinds"])


def test_model_route_version_sample_resolves_to_executable_route_catalogue() -> None:
    catalogue = default_route_catalogue()
    route_version = _sample("contracts/llm_provider/samples/model_route_version.sample.json")
    provider_catalogue = _sample("contracts/llm_provider/samples/provider_catalogue.sample.json")

    selected_model = route_version["selected_model"]
    entry = catalogue.get(selected_model["runtime_route_id"])
    assert entry.provider_id == selected_model["provider_id"]
    assert entry.model_id == selected_model["model_id"]

    declared_models = {
        (provider["provider_id"], model["model_id"]): model
        for provider in provider_catalogue["providers"]
        for model in provider["supported_models"]
    }
    declared_model = declared_models[(selected_model["provider_id"], selected_model["model_id"])]
    assert route_version["route_key"]["task_kind"] in declared_model["supported_task_kinds"]
    assert declared_model["supports_structured_output"] is True
    assert route_version["promotion"]["eval_required"] is True
    assert (
        "chorus/eval/fixtures/uc1_happy_path.json"
        in route_version["promotion"]["eval_fixture_refs"]
    )

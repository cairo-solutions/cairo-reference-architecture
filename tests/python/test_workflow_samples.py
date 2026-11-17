"""Samples the intake workflow documents as schema instances.

``workflows/client-intake-agent/README.md`` says
``intake-request.schema.json`` is what the webhook accepts and
``llm-qualification.schema.json`` is what the LLM must return. The Validate &
Normalize node reads ``json.body``, so the intake schema applies to that
object rather than the n8n item envelope. ``samples/`` holds the example
request, the bad request, and the expected LLM output.

Code-node return values are not asserted. The repository does not define a
schema for ``{valid, errors, lead}`` or for the qualification object after the
node adds ``needs_human_review`` and ``reason``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from schema_contracts import (
    REPO_ROOT,
    error_keywords,
    load_json,
    load_object,
    validator_for_schema,
)

_WORKFLOW = REPO_ROOT / "workflows" / "client-intake-agent"
_INTAKE = _WORKFLOW / "schemas" / "intake-request.schema.json"
_QUALIFICATION = _WORKFLOW / "schemas" / "llm-qualification.schema.json"
_SAMPLES = _WORKFLOW / "samples"


def _body(path: Path) -> Any:
    document = load_object(path)
    assert "body" in document, path
    return document["body"]


def test_valid_request_body_matches_intake_schema() -> None:
    validator = validator_for_schema(load_object(_INTAKE))
    assert error_keywords(validator, _body(_SAMPLES / "valid-request.json")) == set()


def test_valid_request_envelope_is_not_the_intake_instance() -> None:
    validator = validator_for_schema(load_object(_INTAKE))
    keywords = error_keywords(validator, load_json(_SAMPLES / "valid-request.json"))
    assert "required" in keywords
    assert "additionalProperties" in keywords


def test_invalid_request_body_fails_targeted_keywords() -> None:
    validator = validator_for_schema(load_object(_INTAKE))
    found: dict[str, set[str]] = {}
    for error in validator.iter_errors(_body(_SAMPLES / "invalid-request.json")):
        path = tuple(error.absolute_path)
        if not path or not isinstance(path[0], str) or not isinstance(error.validator, str):
            continue
        found.setdefault(path[0], set()).add(error.validator)

    assert "minLength" in found["first_name"]
    assert "format" in found["email"]
    assert "minLength" in found["message"]


def test_expected_llm_output_matches_qualification_schema() -> None:
    validator = validator_for_schema(load_object(_QUALIFICATION))
    assert error_keywords(validator, load_json(_SAMPLES / "expected-llm-output.json")) == set()

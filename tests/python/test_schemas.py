"""Contract checks for every ``*.schema.json`` file in the repository."""

from __future__ import annotations

from pathlib import Path

import pytest

from schema_contracts import (
    REPO_ROOT,
    discover_schema_files,
    error_keywords,
    fixture_dir,
    load_json,
    load_object,
    schema_key,
    validator_for_schema,
)

SCHEMAS = discover_schema_files()


def _schema_id(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _example_params(pattern: str) -> list[pytest.ParameterSet]:
    params: list[pytest.ParameterSet] = []
    for schema_path in SCHEMAS:
        directory = fixture_dir(schema_path)
        if not directory.is_dir():
            continue
        for fixture in sorted(directory.glob(pattern)):
            params.append(
                pytest.param(
                    schema_path,
                    fixture,
                    id=f"{schema_key(schema_path)}/{fixture.name}",
                )
            )
    return params


def test_repository_has_schema_files() -> None:
    assert SCHEMAS, "expected at least one *.schema.json file"


def test_schema_fixture_keys_are_unique() -> None:
    keys = [schema_key(path) for path in SCHEMAS]
    assert len(keys) == len(set(keys))


@pytest.mark.parametrize("schema_path", SCHEMAS, ids=_schema_id)
def test_schema_document_matches_declared_draft(schema_path: Path) -> None:
    validator_for_schema(load_object(schema_path))


@pytest.mark.parametrize("schema_path", SCHEMAS, ids=_schema_id)
def test_schema_has_synthetic_examples(schema_path: Path) -> None:
    directory = fixture_dir(schema_path)
    valid = sorted(directory.glob("valid*.json"))
    invalid = sorted(path for path in directory.glob("invalid-*.json") if path.is_file())
    assert valid, f"{schema_key(schema_path)} needs at least one valid*.json fixture"
    assert invalid, f"{schema_key(schema_path)} needs at least one invalid-*.json fixture"


@pytest.mark.parametrize(
    ("schema_path", "fixture_path"),
    _example_params("valid*.json"),
)
def test_valid_example(schema_path: Path, fixture_path: Path) -> None:
    validator = validator_for_schema(load_object(schema_path))
    assert error_keywords(validator, load_json(fixture_path)) == set()


@pytest.mark.parametrize(
    ("schema_path", "fixture_path"),
    _example_params("invalid-*.json"),
)
def test_invalid_example(schema_path: Path, fixture_path: Path) -> None:
    expected = fixture_path.stem.split("-", 1)[1]
    validator = validator_for_schema(load_object(schema_path))
    keywords = error_keywords(validator, load_json(fixture_path))
    assert expected in keywords, keywords

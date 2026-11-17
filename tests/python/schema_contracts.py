"""Load JSON Schemas and validate instances against the declared draft.

``format`` is an annotation in the draft 2020-12 meta-schema unless a format
checker is supplied. These checks opt in, because the intake schema declares
``format: email`` and the workflow treats email format as a constraint.
jsonschema's built-in ``email`` checker only requires an ``@`` character. It is
not the regular expression used by the workflow's Validate & Normalize node.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

from jsonschema.protocols import Validator
from jsonschema.validators import validator_for

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"

_SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "node_modules",
        "venv",
    }
)


def discover_schema_files(root: Path = REPO_ROOT) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name for name in dirnames if name not in _SKIP_DIRS and not name.startswith(".")
        ]
        for filename in filenames:
            if filename.endswith(".schema.json"):
                found.append(Path(dirpath) / filename)
    return sorted(found)


def schema_key(schema_path: Path) -> str:
    suffix = ".schema.json"
    name = schema_path.name
    if not name.endswith(suffix):
        raise AssertionError(f"{schema_path} is not a *.schema.json file")
    return name[: -len(suffix)]


def fixture_dir(schema_path: Path) -> Path:
    return FIXTURES / schema_key(schema_path)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_object(path: Path) -> dict[str, Any]:
    value = load_json(path)
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return cast("dict[str, Any]", value)


def _same_draft(declared: str, meta_id: str) -> bool:
    """Compare draft URIs, ignoring a single trailing ``#``."""
    return declared.rstrip("#") == meta_id.rstrip("#")


def validator_for_schema(schema: dict[str, Any]) -> Validator:
    """Return a format-checking validator after ``check_schema`` succeeds.

    An unknown ``$schema`` is a failure. ``validator_for`` would otherwise
    fall back to jsonschema's latest draft.
    """
    draft = schema.get("$schema")
    if not isinstance(draft, str) or draft == "":
        raise AssertionError("schema is missing a declared $schema draft URI")

    selected = validator_for(schema)
    meta_id = selected.META_SCHEMA.get("$id")
    if not isinstance(meta_id, str) or not _same_draft(draft, meta_id):
        raise AssertionError(
            f"declared $schema {draft} did not select a matching validator ({selected.__name__})"
        )

    selected.check_schema(cast("dict[Any, Any]", schema))
    return selected(schema, format_checker=selected.FORMAT_CHECKER)


def error_keywords(validator: Validator, instance: Any) -> set[str]:
    keywords: set[str] = set()
    for error in validator.iter_errors(instance):
        if isinstance(error.validator, str):
            keywords.add(error.validator)
    return keywords

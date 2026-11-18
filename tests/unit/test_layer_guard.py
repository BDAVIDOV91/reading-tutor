"""Every test module declares exactly one layer, matching its directory.

Same idea as pdfx's spec-group-tags guard: an untagged test belongs to no layer, so `pytest -m unit` (or
integration / e2e) silently skips it while a targeted run still passes.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

TESTS = Path(__file__).resolve().parents[1]
LAYERS = ("unit", "integration", "e2e")


def _declared_layers(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    layers: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets):
            continue
        values = node.value.elts if isinstance(node.value, (ast.List, ast.Tuple)) else [node.value]
        for v in values:
            # pytest.mark.<layer>
            if isinstance(v, ast.Attribute) and v.attr in LAYERS:
                layers.append(v.attr)
    return layers


def _test_modules() -> list[Path]:
    return sorted(p for p in TESTS.rglob("test_*.py") if "cases" not in p.parts)


def test_test_modules_exist_in_every_layer_dir_that_exists():
    assert _test_modules(), "no test modules found"


@pytest.mark.parametrize("path", _test_modules(), ids=lambda p: str(p.relative_to(TESTS)))
def test_module_declares_its_directory_layer(path: Path):
    layer_dir = path.relative_to(TESTS).parts[0]
    assert layer_dir in LAYERS, f"{path.name} must live under tests/unit, tests/integration or tests/e2e"
    declared = _declared_layers(path)
    assert declared == [layer_dir], (
        f"{path.relative_to(TESTS)} must set `pytestmark = pytest.mark.{layer_dir}` (found {declared or 'none'})"
    )


def test_guard_catches_an_untagged_module(tmp_path: Path):
    untagged = tmp_path / "test_x.py"
    untagged.write_text("def test_a():\n    pass\n", encoding="utf-8")
    assert _declared_layers(untagged) == []
    tagged = tmp_path / "test_y.py"
    tagged.write_text("import pytest\npytestmark = pytest.mark.integration\n", encoding="utf-8")
    assert _declared_layers(tagged) == ["integration"]

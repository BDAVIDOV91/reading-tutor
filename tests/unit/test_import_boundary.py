"""R11: the core (normalise, judge, align, score) imports nothing from UI, network, engine or browser code.

An allow-list, not a deny-list: any new import in src/reading_tutor/core/ must be added here on purpose.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

CORE = Path(__file__).resolve().parents[2] / "src" / "reading_tutor" / "core"

ALLOWED_TOP_LEVEL = {
    "__future__",
    "collections",
    "dataclasses",
    "enum",
    "functools",
    "math",
    "re",
    "typing",
    "unicodedata",
    "rapidfuzz",  # the core's only runtime dependency (plan Q8)
    "reading_tutor",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import inside the core
                continue
            names.add((node.module or "").split(".")[0])
    return names


def test_core_package_exists():
    assert (CORE / "__init__.py").is_file()


@pytest.mark.parametrize("path", sorted(CORE.rglob("*.py")), ids=lambda p: p.name)
def test_core_module_imports_only_allowed(path: Path):
    extra = _imports(path) - ALLOWED_TOP_LEVEL
    assert not extra, f"{path.name} imports {sorted(extra)}; the core must stay free of UI/network/engine code"


def test_importing_core_loads_no_forbidden_module():
    forbidden = ["socket", "http", "urllib", "sqlite3", "asyncio", "torch", "faster_whisper", "fastapi"]
    code = (
        "import sys, reading_tutor.core\n"
        f"bad = [m for m in {forbidden!r} if m in sys.modules]\n"
        "print(','.join(bad))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == ""

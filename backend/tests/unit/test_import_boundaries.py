"""Dependency-direction guard (PRD §7.4): domain/ must not import API
frameworks, orchestration frameworks, provider SDKs, or persistence."""

from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_ROOTS = {
    "fastapi",
    "pydantic_settings",
    "langchain",
    "langchain_core",
    "langgraph",
    "groq",
    "chromadb",
    "sqlalchemy",
    "alembic",
    "httpx",
    "sentence_transformers",
}

DOMAIN_DIR = Path(__file__).resolve().parents[2] / "app" / "domain"


def _imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_domain_imports_only_allowed_roots() -> None:
    violations: list[str] = []
    for py_file in sorted(DOMAIN_DIR.rglob("*.py")):
        roots = _imports_of(py_file)
        forbidden = roots & FORBIDDEN_ROOTS
        if forbidden:
            violations.append(f"{py_file.name}: {sorted(forbidden)}")
    assert not violations, f"Dependency-direction violations: {violations}"

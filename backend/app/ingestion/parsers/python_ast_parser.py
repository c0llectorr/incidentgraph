"""Python AST parsing (PRD FR-09, §9.2).

Uses only the standard library `ast`. Preserves decorator-inclusive spans and
parent class context so a method chunk is understandable even when retrieved
independently. Parse failures are recorded, never silently discarded (FR-10).
"""

from __future__ import annotations

import ast

from app.ingestion.parsers.base import ParsedFile, SymbolDef

_DEFINITION_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _kind_of(node: ast.AST) -> str:
    if isinstance(node, ast.AsyncFunctionDef):
        return "async_function"
    if isinstance(node, ast.FunctionDef):
        return "function"
    return "class"


def _decorator_start(node: ast.AST) -> int:
    decorators = getattr(node, "decorator_list", None)
    if decorators:
        return min(decorator.lineno for decorator in decorators)
    return node.lineno  # type: ignore[attr-defined]


def parse_python(source: str, path: str) -> ParsedFile:
    lines = source.splitlines()
    parsed = ParsedFile(path=path, language="python", total_lines=len(lines))
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        parsed.parse_error = f"SyntaxError: {exc.msg} (line {exc.lineno})"
        return parsed

    symbols: list[SymbolDef] = []
    seen: set[tuple[str, int, int]] = set()

    def visit(node: ast.AST, parent: str | None) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, _DEFINITION_TYPES):
                start = _decorator_start(child)
                end = getattr(child, "end_lineno", None) or child.lineno
                name = f"{parent}.{child.name}" if parent else child.name
                key = (name, start, end)
                if key not in seen:
                    seen.add(key)
                    symbols.append(
                        SymbolDef(
                            name=name,
                            kind=_kind_of(child),
                            start_line=start,
                            end_line=end,
                            parent=parent if parent else None,
                            docstring=ast.get_docstring(child),
                        )
                    )
                # Class bodies are descended into (methods become chunks);
                # function bodies are NOT descended into — nested helpers stay
                # inside their parent chunk, which keeps spans non-duplicated
                # for functions while still satisfying §9.2 nested-definition
                # handling (a nested class inside a function is reachable
                # through the parent chunk).
                if isinstance(child, ast.ClassDef):
                    visit(child, name)
            else:
                visit(child, parent)

    visit(tree, None)
    symbols.sort(key=lambda symbol: (symbol.start_line, symbol.end_line))
    parsed.symbols = symbols
    return parsed

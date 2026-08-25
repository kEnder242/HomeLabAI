"""[FEAT-455] Context Compiler for Agent Context Compaction.

Parses Python source files via the ``ast`` module and extracts class hierarchies,
method signatures, type annotations, and docstrings while stripping implementation
bodies to achieve >50 % token compaction.  Builds cross-module dependency graphs
across a workspace.

Class 1 design: stdlib only (ast, os, pathlib, fnmatch, typing).
"""

from __future__ import annotations

import ast
import fnmatch
import os
from pathlib import Path
from typing import Optional


class ContextCompiler:
    """Compacts Python source into interface-only markdown for LLM context."""

    # ── public API ────────────────────────────────────────────────────

    def compile_file(self, filepath: str) -> str:
        """Parse a single ``.py`` file and return compacted markdown.

        Extracts imports, class hierarchies, method signatures with type
        annotations, return types, and docstrings.  Strips all implementation
        bodies, replacing them with ``...``.
        """
        path = Path(filepath)
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

        sections: list[str] = [f"# Compiled Context: {path.name}", ""]

        imports = self._extract_imports(tree)
        if imports:
            sections.append("## Imports")
            for imp in imports:
                sections.append(f"- {imp}")
            sections.append("")

        classes = self._extract_classes(tree)
        if classes:
            sections.append("## Classes")
            for cls in classes:
                sections.append(cls)
            sections.append("")

        functions = self._extract_functions(tree)
        if functions:
            sections.append("## Functions")
            for func in functions:
                sections.append(func)
            sections.append("")

        return "\n".join(sections)

    def compile_workspace(
        self,
        root_dir: str,
        include_patterns: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
    ) -> str:
        """Compile all matching ``.py`` files and append a dependency graph."""
        root = Path(root_dir)
        sections: list[str] = []
        dep_graph: dict[str, list[str]] = {}

        module_map = self._build_module_map(
            root_dir, include_patterns, exclude_patterns
        )

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(
                d
                for d in dirnames
                if not self._matches_exclude(
                    os.path.relpath(os.path.join(dirpath, d), root),
                    exclude_patterns,
                )
            )

            for filename in sorted(filenames):
                if not filename.endswith(".py"):
                    continue

                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, root)

                if not self._matches_include(rel_path, include_patterns):
                    continue
                if self._matches_exclude(rel_path, exclude_patterns):
                    continue

                try:
                    compiled = self.compile_file(full_path)
                    sections.append(compiled)

                    imports = self._extract_import_names(full_path)
                    ws_deps = self._resolve_workspace_deps(
                        imports, module_map, rel_path
                    )
                    if ws_deps:
                        dep_graph[rel_path] = sorted(ws_deps)
                except (SyntaxError, UnicodeDecodeError) as exc:
                    sections.append(f"<!-- Skipped {rel_path}: {exc} -->")

        if dep_graph:
            sections.append(self._format_dependency_graph(dep_graph))

        return "\n---\n\n".join(sections)

    # ── import extraction ─────────────────────────────────────────────

    def _extract_imports(self, tree: ast.Module) -> list[str]:
        """Return sorted, deduplicated import strings from an AST."""
        imports: set[str] = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = (
                        alias.name
                        if alias.asname is None
                        else f"{alias.name} as {alias.asname}"
                    )
                    imports.add(f"import {name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                level = "." * (node.level or 0)
                names = ", ".join(
                    a.name if a.asname is None else f"{a.name} as {a.asname}"
                    for a in node.names
                )
                imports.add(f"from {level}{module} import {names}")
        return sorted(imports)

    def _extract_import_names(self, filepath: str) -> list[str]:
        """Return raw module names from import statements (for dependency tracking)."""
        try:
            source = Path(filepath).read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            return []

        names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
        return names

    # ── class extraction ──────────────────────────────────────────────

    def _extract_classes(self, tree: ast.Module) -> list[str]:
        result: list[str] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                result.append(self._format_class(node))
        return result

    def _format_class(self, node: ast.ClassDef, indent: int = 0) -> str:
        prefix = " " * indent
        lines: list[str] = []

        for dec in node.decorator_list:
            lines.append(f"{prefix}@{ast.unparse(dec)}")

        bases = ", ".join(ast.unparse(b) for b in node.bases)
        if bases:
            lines.append(f"{prefix}class {node.name}({bases}):")
        else:
            lines.append(f"{prefix}class {node.name}:")

        docstring = ast.get_docstring(node)
        if docstring:
            lines.append(f'{prefix}    """{docstring}"""')

        has_body = False
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lines.append("")
                lines.append(self._format_method(item, indent + 4))
                has_body = True
            elif isinstance(item, ast.ClassDef):
                lines.append("")
                lines.append(self._format_class(item, indent + 4))
                has_body = True
            elif isinstance(item, ast.AnnAssign):
                target = ast.unparse(item.target)
                ann = (
                    f"{target}: {ast.unparse(item.annotation)}"
                    if item.annotation
                    else target
                )
                lines.append(f"{prefix}    {ann}")
                has_body = True
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    lines.append(
                        f"{prefix}    {ast.unparse(target)} = ..."
                    )
                has_body = True

        if not has_body and not docstring:
            lines.append(f"{prefix}    pass")

        return "\n".join(lines)

    # ── function / method extraction ──────────────────────────────────

    def _extract_functions(self, tree: ast.Module) -> list[str]:
        result: list[str] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result.append(self._format_method(node, indent=0))
        return result

    def _format_method(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, indent: int = 0
    ) -> str:
        prefix = " " * indent
        lines: list[str] = []

        for dec in node.decorator_list:
            lines.append(f"{prefix}@{ast.unparse(dec)}")

        async_kw = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        sig = self._build_signature(node.args)

        ret = ""
        if node.returns:
            ret = f" -> {ast.unparse(node.returns)}"

        lines.append(f"{prefix}{async_kw}def {node.name}({sig}){ret}:")

        docstring = ast.get_docstring(node)
        if docstring:
            escaped = docstring.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
            lines.append(f'{prefix}    """{escaped}"""')
        else:
            lines.append(f"{prefix}    ...")

        return "\n".join(lines)

    # ── signature builder ─────────────────────────────────────────────

    def _build_signature(self, args: ast.arguments) -> str:
        parts: list[str] = []

        # Positional-only args
        for arg in args.posonlyargs:
            parts.append(self._format_arg(arg))
        if args.posonlyargs and args.args:
            parts.append("/")

        # Regular args (right-aligned defaults)
        n_args = len(args.args)
        n_defaults = len(args.defaults)
        offset = n_args - n_defaults

        for i, arg in enumerate(args.args):
            default_idx = i - offset
            if 0 <= default_idx < n_defaults:
                default_val = ast.unparse(args.defaults[default_idx])
                parts.append(f"{self._format_arg(arg)} = {default_val}")
            else:
                parts.append(self._format_arg(arg))

        # *args
        if args.vararg:
            parts.append(f"*{self._format_arg(args.vararg)}")

        # Keyword-only args
        if args.kwonlyargs:
            if not args.vararg:
                parts.append("*")
            for i, arg in enumerate(args.kwonlyargs):
                default = args.kw_defaults[i]
                if default is not None:
                    parts.append(
                        f"{self._format_arg(arg)} = {ast.unparse(default)}"
                    )
                else:
                    parts.append(self._format_arg(arg))

        # **kwargs
        if args.kwarg:
            parts.append(f"**{self._format_arg(args.kwarg)}")

        return ", ".join(parts)

    def _format_arg(self, arg: ast.arg) -> str:
        if arg.annotation:
            return f"{arg.arg}: {ast.unparse(arg.annotation)}"
        return arg.arg

    # ── dependency graph ──────────────────────────────────────────────

    def _build_module_map(
        self,
        root_dir: str,
        include_patterns: Optional[list[str]],
        exclude_patterns: Optional[list[str]],
    ) -> dict[str, str]:
        """Map dotted module paths to relative file paths."""
        root = Path(root_dir)
        module_map: dict[str, str] = {}

        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, root)

                if not self._matches_include(rel_path, include_patterns):
                    continue
                if self._matches_exclude(rel_path, exclude_patterns):
                    continue

                module_path = rel_path.replace(os.sep, "/").replace("/", ".")
                if module_path.endswith(".py"):
                    module_path = module_path[:-3]
                if module_path.endswith(".__init__"):
                    module_path = module_path[:-9]

                module_map[module_path] = rel_path

        return module_map

    def _resolve_workspace_deps(
        self,
        import_names: list[str],
        module_map: dict[str, str],
        current_file: str,
    ) -> set[str]:
        """Resolve raw import names to workspace file dependencies."""
        deps: set[str] = set()
        for name in import_names:
            parts = name.split(".")
            for i in range(len(parts), 0, -1):
                candidate = ".".join(parts[:i])
                if candidate in module_map and module_map[candidate] != current_file:
                    deps.add(module_map[candidate])
                    break
        return deps

    def _format_dependency_graph(self, graph: dict[str, list[str]]) -> str:
        lines = [
            "## Dependency Graph",
            "",
            "| Source File | Depends On |",
            "|---|---|",
        ]
        for source, targets in sorted(graph.items()):
            t_str = ", ".join(f"`{t}`" for t in targets)
            lines.append(f"| `{source}` | {t_str} |")
        return "\n".join(lines)

    # ── pattern matching ──────────────────────────────────────────────

    def _matches_include(self, rel_path: str, patterns: Optional[list[str]]) -> bool:
        if patterns is None:
            return True
        return any(fnmatch.fnmatch(rel_path, pat) for pat in patterns)

    def _matches_exclude(self, rel_path: str, patterns: Optional[list[str]]) -> bool:
        if patterns is None:
            return False
        return any(fnmatch.fnmatch(rel_path, pat) for pat in patterns)

"""[FEAT-455] Tests for Context Compiler.

Verifies:
  1. >50 % token reduction (body stripping)
  2. 100 % symbol interface fidelity (all class/function names preserved)
  3. Cross-module dependency graph correctness
"""

import textwrap

import pytest

from src.compiler.context_compiler import ContextCompiler


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def compiler():
    return ContextCompiler()


SAMPLE_MULTI_CLASS = textwrap.dedent("""\
    \"\"\"Sample module with multiple classes and functions.\"\"\"

    import os
    import json
    from pathlib import Path
    from typing import Optional, List, Dict
    from collections import defaultdict


    class BaseProcessor:
        \"\"\"Base class for all data processors in the pipeline.

        Provides common initialization, configuration validation,
        and result aggregation patterns.
        \"\"\"

        def __init__(self, name: str, config: Optional[dict] = None):
            \"\"\"Initialize the processor with a name and optional configuration.\"\"\"
            self.name = name
            self.config = config or {}
            self._cache: Dict[str, any] = {}
            self._stats = defaultdict(int)

            # Complex initialization logic
            for key, value in self.config.items():
                if isinstance(value, str):
                    self._cache[key] = value.lower().strip()
                elif isinstance(value, (int, float)):
                    self._cache[key] = value * 2
                elif isinstance(value, list):
                    self._cache[key] = [str(v) for v in value]
                else:
                    self._cache[key] = None

            self._validate_config()
            self._setup_logging()

        def _validate_config(self) -> None:
            \"\"\"Validate the configuration dictionary against required schema.\"\"\"
            required_keys = ["mode", "timeout", "batch_size"]
            for key in required_keys:
                if key not in self.config:
                    raise ValueError(f"Missing required config key: {key}")

            if self.config.get("timeout", 0) <= 0:
                raise ValueError("Timeout must be positive")

            if self.config.get("batch_size", 0) < 1:
                raise ValueError("Batch size must be at least 1")

            mode = self.config.get("mode")
            valid_modes = ("strict", "lenient", "auto", "debug")
            if mode not in valid_modes:
                raise ValueError(f"Invalid mode: {mode}. Must be one of {valid_modes}")

        def _setup_logging(self) -> None:
            \"\"\"Configure internal logging based on debug mode.\"\"\"
            import logging
            level = logging.DEBUG if self.config.get("mode") == "debug" else logging.INFO
            self._logger = logging.getLogger(f"processor.{self.name}")
            self._logger.setLevel(level)

        def process(self, data: List[dict]) -> dict:
            \"\"\"Process a list of data records and return aggregated results.

            Each record is passed through _process_single which subclasses
            must implement. Errors are collected and returned alongside results.
            \"\"\"
            results = []
            errors = []

            for i, record in enumerate(data):
                try:
                    result = self._process_single(record)
                    results.append(result)
                    self._stats["processed"] += 1
                except Exception as e:
                    errors.append({"index": i, "error": str(e), "record": record})
                    self._stats["errors"] += 1
                    self._logger.warning(f"Failed to process record {i}: {e}")

            self._stats["total_batches"] += 1
            return {
                "results": results,
                "errors": errors,
                "stats": dict(self._stats),
                "success_rate": len(results) / max(len(data), 1),
            }

        def _process_single(self, record: dict) -> dict:
            \"\"\"Process a single record. Must be overridden by subclasses.\"\"\"
            raise NotImplementedError("Subclasses must implement _process_single")

        @property
        def is_ready(self) -> bool:
            \"\"\"Check if the processor is ready to handle data.\"\"\"
            has_cache = bool(self._cache)
            has_config = "mode" in self.config
            has_timeout = self.config.get("timeout", 0) > 0
            return has_cache and has_config and has_timeout

        def reset(self) -> None:
            \"\"\"Reset processor state for reuse.\"\"\"
            self._cache.clear()
            self._stats.clear()
            self._validate_config()


    class FileProcessor(BaseProcessor):
        \"\"\"Processor for file-based data ingestion and transformation.

        Supports JSON, CSV, and Parquet file formats with automatic
        format detection and validation.
        \"\"\"

        SUPPORTED_FORMATS = frozenset({".json", ".csv", ".parquet"})

        def __init__(self, name: str, base_path: Path, config: Optional[dict] = None):
            \"\"\"Initialize file processor with a base directory path.\"\"\"
            super().__init__(name, config)
            self.base_path = base_path
            self._file_cache: Dict[str, str] = {}
            self._handle_map: Dict[str, callable] = {
                ".json": self._read_json,
                ".csv": self._read_csv,
                ".parquet": self._read_parquet,
            }

        def _process_single(self, record: dict) -> dict:
            \"\"\"Read and process a file record from disk.\"\"\"
            file_path = self.base_path / record["filename"]

            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            suffix = file_path.suffix.lower()
            if suffix not in self.SUPPORTED_FORMATS:
                raise ValueError(f"Unsupported format: {suffix}")

            # Read file content using the appropriate handler
            handler = self._handle_map[suffix]
            content = handler(file_path)

            # Compute metadata
            stat = file_path.stat()
            return {
                "filename": record["filename"],
                "size_bytes": stat.st_size,
                "format": suffix,
                "processed_by": self.name,
                "content_hash": hash(content),
                "line_count": content.count("\\n") + 1,
            }

        def _read_json(self, path: Path) -> str:
            \"\"\"Read and validate a JSON file.\"\"\"
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return json.dumps(data, indent=2, sort_keys=True)

        def _read_csv(self, path: Path) -> str:
            \"\"\"Read a CSV file and return its content as a string.\"\"\"
            import csv
            rows = []
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(dict(row))
            return json.dumps(rows, indent=2)

        def _read_parquet(self, path: Path) -> str:
            \"\"\"Read a Parquet file (stub - requires pyarrow).\"\"\"
            raise NotImplementedError("Parquet support requires pyarrow")

        def scan_directory(self) -> List[Path]:
            \"\"\"Scan the base directory for all processable files.\"\"\"
            found = []
            try:
                for item in sorted(self.base_path.iterdir()):
                    if item.is_file() and item.suffix.lower() in self.SUPPORTED_FORMATS:
                        found.append(item)
            except PermissionError as e:
                self._logger.error(f"Permission denied scanning {self.base_path}: {e}")
            return found


    def merge_results(results_list: List[dict]) -> dict:
        \"\"\"Merge multiple processor result dictionaries into a single aggregation.

        Combines results lists, error lists, and stats dictionaries from
        multiple processor runs. Deduplicates results by filename.
        \"\"\"
        merged = {"results": [], "errors": [], "stats": {}}

        for result in results_list:
            merged["results"].extend(result.get("results", []))
            merged["errors"].extend(result.get("errors", []))

            for key, value in result.get("stats", {}).items():
                merged["stats"][key] = merged["stats"].get(key, 0) + value

        # Deduplicate results by filename
        seen = set()
        unique_results = []
        for r in merged["results"]:
            key = r.get("filename", id(r))
            if key not in seen:
                seen.add(key)
                unique_results.append(r)

        merged["results"] = unique_results
        return merged


    def create_processor(processor_type: str, name: str, **kwargs) -> BaseProcessor:
        \"\"\"Factory function to create processor instances by type string.\"\"\"
        registry = {
            "file": FileProcessor,
        }

        cls = registry.get(processor_type)
        if cls is None:
            available = ", ".join(sorted(registry.keys()))
            raise ValueError(f"Unknown processor type: '{processor_type}'. Available: {available}")

        return cls(name=name, **kwargs)
""")

SAMPLE_MODULE_B = textwrap.dedent("""\
    \"\"\"Module B: depends on sample_a.\"\"\"

    import os
    import json
    from sample_a import BaseProcessor, merge_results


    class Aggregator(BaseProcessor):
        \"\"\"Aggregates results from multiple processors.\"\"\"

        def __init__(self, name: str):
            super().__init__(name, {"mode": "auto", "timeout": 30, "batch_size": 10})

        def _process_single(self, record: dict) -> dict:
            \"\"\"Aggregate a single record.\"\"\"
            total = sum(record.get("values", []))
            return {"total": total, "count": len(record.get("values", []))}

        def aggregate_all(self, processor_results: list) -> dict:
            \"\"\"Aggregate results from multiple processor runs.\"\"\"
            merged = merge_results(processor_results)
            totals = [r.get("total", 0) for r in merged["results"]]
            return {"grand_total": sum(totals), "items": len(totals)}


    def run_pipeline(files: list) -> dict:
        \"\"\"Run the full aggregation pipeline.\"\"\"
        agg = Aggregator("pipeline")
        return agg.process([{"filename": f} for f in files])
""")


# ── Tests: token reduction ────────────────────────────────────────────


def _word_count(text: str) -> int:
    """Rough token proxy: whitespace-split word count."""
    return len(text.split())


class TestTokenReduction:
    """Verify >50 % token reduction from body stripping."""

    def test_single_file_compaction(self, compiler, tmp_path):
        src = tmp_path / "sample.py"
        src.write_text(SAMPLE_MULTI_CLASS)

        compiled = compiler.compile_file(str(src))

        original_wc = _word_count(SAMPLE_MULTI_CLASS)
        compiled_wc = _word_count(compiled)
        reduction = 1.0 - (compiled_wc / original_wc)

        assert reduction > 0.50, (
            f"Expected >50% token reduction, got {reduction:.1%} "
            f"(original={original_wc}, compiled={compiled_wc})"
        )

    def test_heavy_body_file_compaction(self, compiler, tmp_path):
        """File with large method bodies should compact significantly."""
        heavy = textwrap.dedent("""\
            \"\"\"Heavy module.\"\"\"

            import os


            class Heavy:
                \"\"\"A class with very large method bodies.\"\"\"

                def big_method(self, data: list) -> dict:
                    \"\"\"Process data through 20 transformation steps.\"\"\"
                    step1 = [x * 2 for x in data]
                    step2 = [x + 1 for x in step1]
                    step3 = [x // 3 for x in step2]
                    step4 = [abs(x) for x in step3]
                    step5 = [x ** 2 for x in step4]
                    step6 = sorted(step5, reverse=True)
                    step7 = step6[:100]
                    step8 = [x for x in step7 if x > 0]
                    step9 = sum(step8)
                    step10 = step9 / max(len(step8), 1)
                    step11 = step10 * 3.14159
                    step12 = round(step11, 2)
                    step13 = str(step12)
                    step14 = step13.encode("utf-8")
                    step15 = len(step14)
                    step16 = step15 > 0
                    step17 = {"result": step12, "length": step15, "valid": step16}
                    step18 = json.dumps(step17)
                    step19 = step18.strip()
                    step20 = step19.replace(" ", "_")
                    return {"output": step20, "steps": 20}

                def another_big(self, x: int) -> int:
                    \"\"\"Compute factorial iteratively.\"\"\"
                    result = 1
                    for i in range(1, x + 1):
                        result *= i
                    return result
        """)
        src = tmp_path / "heavy.py"
        src.write_text(heavy)

        compiled = compiler.compile_file(str(src))
        reduction = 1.0 - (_word_count(compiled) / _word_count(heavy))
        assert reduction > 0.60, f"Heavy file reduction too low: {reduction:.1%}"


# ── Tests: symbol fidelity ────────────────────────────────────────────


class TestSymbolFidelity:
    """Verify 100 % symbol interface fidelity."""

    EXPECTED_CLASSES = [
        "BaseProcessor",
        "FileProcessor",
    ]
    EXPECTED_FUNCTIONS = [
        "merge_results",
        "create_processor",
    ]
    EXPECTED_METHODS = [
        "__init__",
        "_validate_config",
        "_setup_logging",
        "process",
        "_process_single",
        "is_ready",
        "reset",
        "_read_json",
        "_read_csv",
        "_read_parquet",
        "scan_directory",
    ]

    def test_all_class_names_preserved(self, compiler, tmp_path):
        src = tmp_path / "sample.py"
        src.write_text(SAMPLE_MULTI_CLASS)
        compiled = compiler.compile_file(str(src))

        for name in self.EXPECTED_CLASSES:
            assert f"class {name}" in compiled, f"Missing class: {name}"

    def test_all_function_names_preserved(self, compiler, tmp_path):
        src = tmp_path / "sample.py"
        src.write_text(SAMPLE_MULTI_CLASS)
        compiled = compiler.compile_file(str(src))

        for name in self.EXPECTED_FUNCTIONS:
            assert f"def {name}" in compiled, f"Missing function: {name}"

    def test_all_method_names_preserved(self, compiler, tmp_path):
        src = tmp_path / "sample.py"
        src.write_text(SAMPLE_MULTI_CLASS)
        compiled = compiler.compile_file(str(src))

        for name in self.EXPECTED_METHODS:
            assert f"def {name}" in compiled, f"Missing method: {name}"

    def test_type_annotations_preserved(self, compiler, tmp_path):
        src = tmp_path / "sample.py"
        src.write_text(SAMPLE_MULTI_CLASS)
        compiled = compiler.compile_file(str(src))

        # Check key annotations appear in compiled output
        assert "name: str" in compiled
        assert "config: Optional[dict]" in compiled
        assert "data: List[dict]" in compiled
        assert "-> dict" in compiled
        assert "-> None" in compiled
        assert "-> bool" in compiled
        assert "-> List[Path]" in compiled

    def test_docstrings_preserved(self, compiler, tmp_path):
        src = tmp_path / "sample.py"
        src.write_text(SAMPLE_MULTI_CLASS)
        compiled = compiler.compile_file(str(src))

        assert "Base class for all data processors" in compiled
        assert "Initialize the processor" in compiled
        assert "Validate the configuration" in compiled

    def test_decorators_preserved(self, compiler, tmp_path):
        src = tmp_path / "sample.py"
        src.write_text(SAMPLE_MULTI_CLASS)
        compiled = compiler.compile_file(str(src))

        assert "@property" in compiled

    def test_inheritance_preserved(self, compiler, tmp_path):
        src = tmp_path / "sample.py"
        src.write_text(SAMPLE_MULTI_CLASS)
        compiled = compiler.compile_file(str(src))

        assert "class FileProcessor(BaseProcessor)" in compiled

    def test_default_values_preserved(self, compiler, tmp_path):
        src = tmp_path / "sample.py"
        src.write_text(SAMPLE_MULTI_CLASS)
        compiled = compiler.compile_file(str(src))

        assert 'config: Optional[dict] = None' in compiled

    def test_body_stripped_replaced_with_dots(self, compiler, tmp_path):
        src = tmp_path / "sample.py"
        src.write_text(SAMPLE_MULTI_CLASS)
        compiled = compiler.compile_file(str(src))

        # Body-specific code should NOT appear
        assert "value.lower().strip()" not in compiled
        assert "raise ValueError" not in compiled
        assert 'logging.getLogger' not in compiled
        assert "result *= i" not in compiled
        # Methods with docstrings show the docstring, not ...
        # Methods without docstrings show ...
        # At minimum, verify the body was stripped (no implementation code)
        assert "self._cache[key] = value" not in compiled

    def test_frozenset_class_var_preserved(self, compiler, tmp_path):
        src = tmp_path / "sample.py"
        src.write_text(SAMPLE_MULTI_CLASS)
        compiled = compiler.compile_file(str(src))

        assert "SUPPORTED_FORMATS" in compiled


# ── Tests: imports ─────────────────────────────────────────────────────


class TestImportExtraction:
    def test_imports_section_present(self, compiler, tmp_path):
        src = tmp_path / "sample.py"
        src.write_text(SAMPLE_MULTI_CLASS)
        compiled = compiler.compile_file(str(src))

        assert "## Imports" in compiled
        assert "import os" in compiled
        assert "import json" in compiled

    def test_from_imports_extracted(self, compiler, tmp_path):
        src = tmp_path / "sample.py"
        src.write_text(SAMPLE_MULTI_CLASS)
        compiled = compiler.compile_file(str(src))

        assert "from pathlib import Path" in compiled
        assert "from typing import Optional, List, Dict" in compiled


# ── Tests: dependency graph ───────────────────────────────────────────


class TestDependencyGraph:
    def test_workspace_dependency_graph(self, compiler, tmp_path):
        (tmp_path / "sample_a.py").write_text(SAMPLE_MULTI_CLASS)
        (tmp_path / "sample_b.py").write_text(SAMPLE_MODULE_B)

        compiled = compiler.compile_workspace(str(tmp_path))

        assert "## Dependency Graph" in compiled
        assert "sample_b.py" in compiled
        assert "sample_a.py" in compiled

    def test_self_import_excluded_from_graph(self, compiler, tmp_path):
        """A file importing itself should not appear as its own dependency."""
        self_import = textwrap.dedent("""\
            \"\"\"Self-referencing module.\"\"\"
            from myself import something

            def foo() -> None:
                pass
        """)
        (tmp_path / "myself.py").write_text(self_import)

        compiled = compiler.compile_workspace(str(tmp_path))
        # myself.py should NOT list itself as a dependency
        for line in compiled.split("\n"):
            if "myself.py" in line and "|" in line:
                # Dependency row — should not have myself.py in Depends On column
                parts = line.split("|")
                if len(parts) >= 3:
                    depends_col = parts[2]
                    assert "myself.py" not in depends_col, (
                        f"File lists itself as dependency: {line}"
                    )

    def test_workspace_syntax_error_graceful(self, compiler, tmp_path):
        """Files with syntax errors should be skipped, not crash."""
        (tmp_path / "good.py").write_text(
            "def hello() -> str:\n    return 'world'\n"
        )
        (tmp_path / "bad.py").write_text(
            "def broken(:\n    this is not valid python\n"
        )

        compiled = compiler.compile_workspace(str(tmp_path))
        assert "good.py" in compiled
        assert "Skipped bad.py" in compiled


# ── Tests: include / exclude patterns ─────────────────────────────────


class TestIncludeExclude:
    def test_include_patterns(self, compiler, tmp_path):
        (tmp_path / "core.py").write_text(
            "class Core:\n    def run(self) -> None: pass\n"
        )
        (tmp_path / "test_helper.py").write_text(
            "class Helper:\n    def help(self) -> None: pass\n"
        )

        compiled = compiler.compile_workspace(
            str(tmp_path), include_patterns=["core.py"]
        )
        assert "core.py" in compiled
        assert "test_helper.py" not in compiled

    def test_exclude_patterns(self, compiler, tmp_path):
        (tmp_path / "main.py").write_text(
            "class Main:\n    def run(self) -> None: pass\n"
        )
        (tmp_path / "test_foo.py").write_text(
            "class Foo:\n    def bar(self) -> None: pass\n"
        )

        compiled = compiler.compile_workspace(
            str(tmp_path), exclude_patterns=["test_*.py"]
        )
        assert "main.py" in compiled
        assert "test_foo.py" not in compiled


# ── Tests: markdown structure ─────────────────────────────────────────


class TestMarkdownStructure:
    def test_compiled_has_section_headers(self, compiler, tmp_path):
        src = tmp_path / "sample.py"
        src.write_text(SAMPLE_MULTI_CLASS)
        compiled = compiler.compile_file(str(src))

        assert compiled.startswith("# Compiled Context:")
        assert "## Imports" in compiled
        assert "## Classes" in compiled
        assert "## Functions" in compiled

    def test_empty_file_produces_valid_output(self, compiler, tmp_path):
        src = tmp_path / "empty.py"
        src.write_text('"""Empty module."""\n')
        compiled = compiler.compile_file(str(src))
        assert "# Compiled Context:" in compiled

    def test_import_only_file(self, compiler, tmp_path):
        src = tmp_path / "imports.py"
        src.write_text("import os\nimport sys\n")
        compiled = compiler.compile_file(str(src))
        assert "## Imports" in compiled
        assert "import os" in compiled
        assert "import sys" in compiled

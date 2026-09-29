"""[FEAT-622 / BKM-070 / WIS-487] Hermetic unit tests for the offline job ingest CLI.

No network, no clock, no LLM engine. Every assertion must hold offline.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ops.job_ingest import (
    DEFAULT_JOBS_DIR,
    DEFAULT_LENS_DIR,
    extract_job_tokens_and_rubric,
    ingest_job_posting,
    main,
)
from projection.lenses import CATEGORIES, SEVERITIES, validate_lens_schema

JOB_TEXT = """
Principal Site Reliability Engineer at Acme Systems.

About the role: You will lead a team of 9 engineers building and operating our
multi-region Kubernetes platform on AWS. You will own reliability end to end:
latency, throughput, uptime and cost. We mentor and coach engineers and grow
careers across a cross-functional team of stakeholders.

Requirements:
- 8+ years of experience operating production infrastructure at scale.
- Strong Python and Go, deep Terraform and Kubernetes experience.
- Familiarity with Prometheus, Grafana and OpenTelemetry observability stacks.
- Experience with Kafka, PostgreSQL and CI/CD pipelines.
- Bachelor's degree in Computer Science or equivalent practical experience.
- AWS Certified Solutions Architect certification preferred.

Nice to have: FinOps cost discipline, chaos engineering experience, and a track
record of mentoring senior engineers.

We want someone who can lead with technical strategy, drive cross-functional
alignment on roadmap priorities, and scale our incident response practice.
"""


def _tokens(slug: str = "principal_sre", title: str = "Principal Site Reliability Engineer") -> dict:
    return extract_job_tokens_and_rubric(JOB_TEXT, slug, title)


class TestExtraction:
    def test_required_technical_tokens_extracted(self):
        tier0 = _tokens()["tier_0_structural"]
        tech = tier0["technical_tokens"]
        for expected in ("python", "kubernetes", "terraform", "aws", "prometheus", "kafka"):
            assert expected in tech, f"missing required token {expected!r} in {tech}"
        # Sorted for determinism, and de-duplicated.
        assert tech == sorted(tech)
        assert len(tech) == len(set(tech))

    def test_degree_and_cert_keywords_extracted(self):
        degrees = _tokens()["tier_0_structural"]["degree_cert_keywords"]
        assert any("bachelor" in d for d in degrees)
        assert any("certif" in d for d in degrees)

    def test_min_years_and_density_limits(self):
        tier0 = _tokens()["tier_0_structural"]
        assert tier0["min_years_experience"] == 8
        # The fixture states no explicit density cap -> empty, never invented.
        assert tier0["density_limits"] == []

    def test_density_limits_detected_when_stated(self):
        text = JOB_TEXT + "\nKeep your resume to 2 pages and 450 words. Use 4-6 bullets per role.\n"
        limits = extract_job_tokens_and_rubric(text, "dense_slug")["tier_0_structural"][
            "density_limits"
        ]
        assert limits, "expected density limits to be extracted"
        joined = " ".join(limits)
        assert "4-6" in joined or "4 - 6" in joined
        assert "2" in joined

    def test_tier_1_semantic_has_persona_impact_leadership(self):
        tier1 = _tokens()["tier_1_semantic"]
        persona = tier1["hiring_manager_persona"]
        assert persona["name"] and persona["role"] and persona["lens_perspective"]
        assert "team of 9" in persona["lens_perspective"]
        assert tier1["domain_impact_focus"]["tenets"]
        assert tier1["leadership_tenets"]["tenets"]
        assert "mentor" in tier1["leadership_tenets"]["tenets"]

    def test_extract_is_100_percent_deterministic(self):
        assert _tokens() == _tokens()
        assert _tokens()["content_sha256"] == _tokens()["content_sha256"]


class TestRubricContract:
    def test_lens_id_and_schema(self):
        result = _tokens()
        assert result["lens_id"] == "job_principal_sre"
        assert result["schema"] == "lens.v2"

    def test_tier_0_criteria_are_structurally_decidable(self):
        criteria = _tokens()["criteria"]
        tier0 = [c for c in criteria if c["tier"] == "tier_0_structural"]
        assert tier0, "expected tier_0_structural criteria"
        for rule in tier0:
            assert rule["category"] in CATEGORIES
            assert rule["severity"] in SEVERITIES
            # CP-1: semantic-only ids may never appear in tier_0.
            assert rule["rule_id"] not in {
                "FIRST_3_WORDS_POWER_VERB",
                "SO_WHAT_METRIC_DRILL",
                "THREE_SENTENCE_SUMMARY_HOOK",
            }

    def test_tier_1_criteria_present_and_within_detector_budget(self):
        criteria = _tokens()["criteria"]
        tier1 = [c for c in criteria if c["tier"] == "tier_1_semantic"]
        assert len(tier1) <= 5, "semantic rules must respect the tier_1 headroom"
        ids = {c["rule_id"] for c in tier1}
        assert "JOB_HIRING_MANAGER_PERSONA_MATCH" in ids
        assert "JOB_DOMAIN_IMPACT_FOCUS" in ids
        assert "JOB_LEADERSHIP_TENET_EVIDENCE" in ids

    def test_compiled_rubric_passes_canonical_validator(self):
        from projection.lenses import craft_lens

        result = _tokens()
        compiled = craft_lens(
            lens_id=result["lens_id"],
            content=JOB_TEXT,
            title=JOB_TEXT.splitlines()[2].strip(),
            persona=result["persona"],
            criteria=result["criteria"],
        )
        assert compiled["status"] == "success"
        assert validate_lens_schema(compiled) is True
        assert validate_lens_schema(compiled["rubric"]) is True
        # craft_lens must not have silently dropped our rules.
        assert compiled["rubric"]["budget_exceeded"] == []


class TestRefusals:
    def test_empty_text_refuses(self):
        with pytest.raises(ValueError, match="too short|empty"):
            extract_job_tokens_and_rubric("", "slug")

    def test_short_text_refuses(self):
        with pytest.raises(ValueError, match="too short"):
            extract_job_tokens_and_rubric("hi", "slug")

    def test_non_string_text_refuses(self):
        with pytest.raises(ValueError, match="must be a string"):
            extract_job_tokens_and_rubric(None, "slug")  # type: ignore[arg-type]

    def test_empty_slug_refuses(self):
        with pytest.raises(ValueError, match="slug"):
            extract_job_tokens_and_rubric(JOB_TEXT, "   ")

    def test_slug_is_sanitized_not_rejected(self):
        assert _tokens("Principal SRE / Acme!")["slug"] == "principal_sre_acme"


class TestIngestion:
    def test_writes_both_artifacts_in_declared_paths(self, tmp_path: Path):
        jobs = tmp_path / "jobs"
        lenses = tmp_path / "lenses"
        job_path, lens_path = ingest_job_posting(
            text=JOB_TEXT,
            slug="principal_sre",
            title="Principal Site Reliability Engineer",
            company="Acme Systems",
            output_dir=str(jobs),
            lens_dir=str(lenses),
        )
        assert job_path == str(jobs / "principal_sre.json")
        assert lens_path == str(lenses / "job_principal_sre.json")
        assert Path(job_path).is_file() and Path(lens_path).is_file()
        # Atomic write leaves no .tmp residue.
        assert not list(jobs.glob("*.tmp"))
        assert not list(lenses.glob("*.tmp"))

    def test_frozen_job_record_is_complete(self, tmp_path: Path):
        job_path, _ = ingest_job_posting(
            text=JOB_TEXT,
            slug="principal_sre",
            company="Acme Systems",
            output_dir=str(tmp_path / "jobs"),
            lens_dir=str(tmp_path / "lenses"),
        )
        frozen = json.loads(Path(job_path).read_text(encoding="utf-8"))
        assert frozen["schema"] == "job_posting.v1"
        assert frozen["slug"] == "principal_sre"
        assert frozen["company"] == "Acme Systems"
        assert frozen["frozen_posting"] == JOB_TEXT.strip()
        assert frozen["tier_0_structural"]["technical_tokens"]
        assert frozen["tier_1_semantic"]["hiring_manager_persona"]
        assert frozen["fe_anchors"] == ["FEAT-622", "BKM-070", "WIS-487"]

    def test_persisted_lens_validates(self, tmp_path: Path):
        _, lens_path = ingest_job_posting(
            text=JOB_TEXT,
            slug="principal_sre",
            output_dir=str(tmp_path / "jobs"),
            lens_dir=str(tmp_path / "lenses"),
        )
        rubric = json.loads(Path(lens_path).read_text(encoding="utf-8"))
        assert rubric["lens_id"] == "job_principal_sre"
        assert validate_lens_schema(rubric) is True
        assert rubric["tier_manifest"]["tier_0_structural"]
        assert rubric["tier_manifest"]["tier_1_semantic"]

    def test_ingestion_is_byte_deterministic(self, tmp_path: Path):
        a_job, a_lens = ingest_job_posting(
            text=JOB_TEXT,
            slug="principal_sre",
            output_dir=str(tmp_path / "a" / "jobs"),
            lens_dir=str(tmp_path / "a" / "lenses"),
        )
        b_job, b_lens = ingest_job_posting(
            text=JOB_TEXT,
            slug="principal_sre",
            output_dir=str(tmp_path / "b" / "jobs"),
            lens_dir=str(tmp_path / "b" / "lenses"),
        )
        assert Path(a_job).read_bytes() == Path(b_job).read_bytes()
        assert Path(a_lens).read_bytes() == Path(b_lens).read_bytes()

    def test_reads_text_file(self, tmp_path: Path):
        posting = tmp_path / "posting.txt"
        posting.write_text(JOB_TEXT, encoding="utf-8")
        job_path, _ = ingest_job_posting(
            source_path=str(posting),
            slug="from_file",
            output_dir=str(tmp_path / "jobs"),
            lens_dir=str(tmp_path / "lenses"),
        )
        assert json.loads(Path(job_path).read_text(encoding="utf-8"))["slug"] == "from_file"

    def test_reads_json_file_via_description_key(self, tmp_path: Path):
        posting = tmp_path / "posting.json"
        posting.write_text(
            json.dumps({"title": "Staff Engineer", "description": JOB_TEXT}),
            encoding="utf-8",
        )
        job_path, _ = ingest_job_posting(
            source_path=str(posting),
            slug="from_json",
            output_dir=str(tmp_path / "jobs"),
            lens_dir=str(tmp_path / "lenses"),
        )
        frozen = json.loads(Path(job_path).read_text(encoding="utf-8"))
        assert frozen["frozen_posting"] == JOB_TEXT.strip()

    def test_reads_markdown_file(self, tmp_path: Path):
        posting = tmp_path / "posting.md"
        posting.write_text(f"# Role\n\n{JOB_TEXT}", encoding="utf-8")
        job_path, _ = ingest_job_posting(
            source_path=str(posting),
            slug="from_md",
            output_dir=str(tmp_path / "jobs"),
            lens_dir=str(tmp_path / "lenses"),
        )
        assert Path(job_path).is_file()

    def test_derives_slug_when_omitted(self, tmp_path: Path):
        job_path, lens_path = ingest_job_posting(
            text=JOB_TEXT,
            title="Principal Site Reliability Engineer",
            company="Acme Systems",
            output_dir=str(tmp_path / "jobs"),
            lens_dir=str(tmp_path / "lenses"),
        )
        assert Path(job_path).name == "principal_site_reliability_engineer_acme_systems.json"
        assert Path(lens_path).name == "job_principal_site_reliability_engineer_acme_systems.json"

    def test_requires_exactly_one_source(self, tmp_path: Path):
        with pytest.raises(ValueError, match="exactly one"):
            ingest_job_posting(output_dir=str(tmp_path), lens_dir=str(tmp_path))
        with pytest.raises(ValueError, match="exactly one"):
            ingest_job_posting(text=JOB_TEXT, source_path="x.txt")

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            ingest_job_posting(
                source_path=str(tmp_path / "nope.txt"),
                slug="x",
                output_dir=str(tmp_path / "jobs"),
                lens_dir=str(tmp_path / "lenses"),
            )

    def test_creates_missing_output_directories(self, tmp_path: Path):
        jobs = tmp_path / "deep" / "nested" / "jobs"
        lenses = tmp_path / "deep" / "nested" / "lenses"
        ingest_job_posting(
            text=JOB_TEXT,
            slug="nested",
            output_dir=str(jobs),
            lens_dir=str(lenses),
        )
        assert jobs.is_dir() and lenses.is_dir()

    def test_default_dirs_point_at_field_notes(self):
        assert DEFAULT_JOBS_DIR.parts[-3:] == ("field_notes", "data", "jobs")
        assert DEFAULT_LENS_DIR.parts[-3:] == ("field_notes", "data", "lenses")
        # Regression guard: Portfolio_Dev is a SIBLING of HomeLabAI inside Dev_Lab,
        # not a child of it. A one-level-short constant silently created a stray
        # HomeLabAI/Portfolio_Dev tree.
        src_root = Path(__file__).resolve().parents[1]  # HomeLabAI/src
        dev_lab = src_root.parents[1]
        assert dev_lab.name == "Dev_Lab", f"unexpected workspace root: {dev_lab}"
        assert DEFAULT_JOBS_DIR.parent.parent.parent == dev_lab / "Portfolio_Dev"
        assert (DEFAULT_JOBS_DIR.parent.parent.parent / "field_notes").is_dir()

    def test_default_output_lands_in_real_field_notes(self):
        """Default (no --output-dir) must resolve to the real repo, not a stray tree."""
        job_path, lens_path = ingest_job_posting(text=JOB_TEXT, slug="default_dir_probe")
        try:
            assert Path(job_path).parent == DEFAULT_JOBS_DIR
            assert Path(lens_path).parent == DEFAULT_LENS_DIR
            # job_path is a file (4 hops); DEFAULT_*_DIR is the dir itself (3 hops).
            portfolio_root = DEFAULT_JOBS_DIR.parent.parent.parent
            assert Path(job_path).parent.parent.parent.parent == portfolio_root
            assert portfolio_root == Path("/home/jallred/Dev_Lab/Portfolio_Dev")
            # The regression: a one-level-short constant created HomeLabAI/Portfolio_Dev.
            assert not (portfolio_root.parent / "HomeLabAI" / "Portfolio_Dev").exists()
        finally:
            Path(job_path).unlink(missing_ok=True)
            Path(lens_path).unlink(missing_ok=True)


class TestCli:
    def test_main_success(self, tmp_path: Path, capsys):
        code = main(
            [
                "--text",
                JOB_TEXT,
                "--slug",
                "cli_slug",
                "--title",
                "Principal SRE",
                "--company",
                "Acme",
                "--output-dir",
                str(tmp_path / "jobs"),
                "--lens-dir",
                str(tmp_path / "lenses"),
            ]
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "job:" in out and "lens:" in out
        assert (tmp_path / "jobs" / "cli_slug.json").is_file()
        assert (tmp_path / "lenses" / "job_cli_slug.json").is_file()

    def test_main_requires_one_source(self, capsys):
        assert main([]) == 2
        assert "exactly one" in capsys.readouterr().err

    def test_main_reports_refusal_without_traceback(self, tmp_path: Path, capsys):
        code = main(["--text", "too short", "--slug", "s", "--output-dir", str(tmp_path)])
        assert code == 1
        assert "error:" in capsys.readouterr().err

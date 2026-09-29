"""[FEAT-622 / BKM-070 / WIS-487] Offline Job & Target Ingestion CLI.

Freezes a raw job posting and compiles it into a deterministic Lens rubric.

The one-liner::

    python3 -m ops.job_ingest --file posting.txt --slug principal_sre --company Acme

The core logic: pure-Python, closed-vocabulary token extraction feeds
``projection.lenses.craft_lens()``, which performs no I/O and no network, then
``projection.lenses.persist_lens()`` performs the atomic ``.tmp`` + ``os.replace``
write required by the Class 1 mandate.

The trigger: any new target role. Point the CLI at a local ``.txt``/``.md``/
``.json`` posting (or pass ``--text``) and it emits two artifacts:

* ``field_notes/data/jobs/<slug>.json``     -- the frozen raw posting.
* ``field_notes/data/lenses/job_<slug>.json`` -- the compiled rubric.

The scars: the detector budget is a *hard* cap -- ``craft_lens`` silently drops
tier_1 criteria beyond 8 rules, so this module caps its own semantic rules at
``_TIER_1_RULE_CAP`` and reports the overflow instead of losing it. A refusal from
``craft_lens`` is raised, never persisted (WIS-487: no silent fallback).

Determinism/hermeticity: no clock, no RNG, no network, no environment reads in
the extraction path. Identical input bytes always produce byte-identical output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# --- Sibling import bootstrap (Class 1: run from src/, from src/ops/, or by path)
_SRC_ROOT = Path(__file__).resolve().parents[1]
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from projection.lenses import (  # import must follow the path bootstrap above
    CATEGORIES,
    MIN_CONTENT_CHARS,
    SEVERITIES,
    TIERS,
    craft_lens,
    persist_lens,
    validate_lens_schema,
)

__all__ = [
    "extract_job_tokens_and_rubric",
    "ingest_job_posting",
    "main",
]

# --- Layout constants --------------------------------------------------------

PORTFOLIO_DIR = _SRC_ROOT.parents[1] / "Portfolio_Dev"
DEFAULT_JOBS_DIR = PORTFOLIO_DIR / "field_notes" / "data" / "jobs"
DEFAULT_LENS_DIR = PORTFOLIO_DIR / "field_notes" / "data" / "lenses"

# Lenses prefixed with this marker are job-target rubrics, not authored playbooks.
JOB_LENS_PREFIX = "job_"

# craft_lens() prepends 3 tier_1 base rules against a tier_1 budget of 8, leaving
# 5 free slots. Cap ourselves so overflow is reported instead of silently dropped.
_TIER_1_RULE_CAP = 5

# --- Closed extraction vocabularies (deterministic, no model) ----------------

_TECH_VOCAB = frozenset(
    """
    python java golang rust c++ c# typescript javascript scala kotlin swift elixir
    haskell clojure erlang matlab perl ruby php sql bash shell
    react angular vue svelte next.js nuxt remix django flask fastapi rails spring
    node.js deno bun graphql grpc rest websocket microservices serverless
    html css sass tailwind webpack vite babel redux
    postgres postgresql mysql mariadb sqlite mongodb redis cassandra dynamodb
    elasticsearch kafka rabbitmq nats sqs airflow dbt snowflake
    bigquery redshift databricks hadoop spark hdfs etl
    aws azure gcp heroku digitalocean vercel cloudflare s3 ec2 lambda ecs
    kubernetes docker podman helm terraform ansible puppet chef
    jenkins circleci travis argocd flux github-actions gitlab-ci devops cicd
    linux unix ubuntu debian systemd nixos networking tcp ip dns tls ssh
    security iam oauth jwt saml sso encryption pentestration compliance
    soc siem gdpr hipaa fedramp nist soc2 iso-27001 pki hsm
    prometheus grafana datadog splunk sentry opentelemetry jaeger
    slo sli incident-response on-call postmortem
    machine-learning deep-learning neural-network nlp llm transformers
    pytorch tensorflow scikit-learn pandas numpy mlops
    api sdk protobuf openapi unit-tests
    """.split()
)

# Closed, deliberately free of bare "ai"/"go"/"c"/"r" which match prose noise.
_DEGREE_RE = re.compile(
    r"\b(?:"
    r"b\.?s\.?c?\.?|bachelor(?:'s)?(?:\s+of\s+science|\s+degree)?|"
    r"m\.?s\.?c?\.?|master(?:'s)?(?:\s+of\s+science|\s+degree)?|"
    r"mba|ph\.?d\.?|doctorate|associate(?:'s)?(?:\s+degree)?|"
    r"degree(?:\s+in\s+[\w\s]{2,30})?|certified|certification|certifications|"
    r"cka|ckad|cks|certified-kubernetes-administrator|cissp|cism|comptia-sec|"
    r"pmp|scrum-master|professional-certification|accredited|"
    r"bootcamp|nanodegree|coursera|udemy"
    r")\b",
    re.IGNORECASE,
)

_SENIORITY_RE = re.compile(
    r"\b(?:intern|junior|entry[- ]level|mid[- ]level|midweight|senior|sr\.?|"
    r"staff|principal|lead|principal-engineer|distinguished|head[- ]of|director|"
    r"vp|vice-president|chief|cto|architect|manager)\b",
    re.IGNORECASE,
)

_LEADERSHIP_TENETS = (
    "mentor",
    "mentorship",
    "coach",
    "coaching",
    "lead",
    "leads",
    "leading",
    "leadership",
    "own",
    "owns",
    "ownership",
    "drive",
    "drives",
    "driving",
    "spearhead",
    "spearheads",
    "cross-functional",
    "crossfunctional",
    "stakeholder",
    "stakeholders",
    "strategy",
    "strategic",
    "roadmap",
    "roadmaps",
    "vision",
    "visionary",
    "delegate",
    "delegation",
    "scale",
    "scalable",
    "scaling",
    "culture",
    "collaborate",
    "collaboration",
    "influence",
    "influence without authority",
    "grow",
    "growing",
    "hire",
    "hiring",
    "talent",
    "team",
    "teams",
)

_IMPACT_TENETS = (
    "reliability",
    "latency",
    "throughput",
    "uptime",
    "availability",
    "scalability",
    "scale",
    "cost",
    "costs",
    "efficiency",
    "performance",
    "resilience",
    "incident",
    "incidents",
    "downtime",
    "slo",
    "sli",
    "capacity",
    "observability",
    "security",
    "compliance",
    "customers",
    "customer",
    "revenue",
    "business",
    "product",
    "roadmap",
    "delivery",
)

_STOPWORDS = frozenset(
    """
    a an the and or of to in for on at by with from as is are be we you our your
    will would should must may can may also this that these those it its they
    them their there here who whom which what when where how all any both each
    more most other some such no nor not only own same so than too very s t don
    now work working works role job position candidate candidates team teams
    company companies experience experienced required require requires
    ability able strong excellent good great new years year experience
    """.split()
)

# Word-boundary safe matching for vocab terms carrying punctuation (c++, ci/cd).
_TOKEN_LOOKBEHIND = r"(?<![A-Za-z0-9_+#.])"
_TOKEN_LOOKAHEAD = r"(?![A-Za-z0-9_+#.])"
_TECH_RE = re.compile(
    _TOKEN_LOOKBEHIND
    + "("
    + "|".join(re.escape(term) for term in sorted(_TECH_VOCAB, key=len, reverse=True))
    + ")"
    + _TOKEN_LOOKAHEAD,
    re.IGNORECASE,
)

# "5+ years", "5-10 years", "8 years of experience" -> minimum required years.
_YEARS_RANGE_RE = re.compile(
    r"\b(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b", re.IGNORECASE
)
_YEARS_MIN_RE = re.compile(r"\b(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b", re.IGNORECASE)

# Density limits: bullet caps, page/word ceilings, length caps.
_DENSITY_PATTERNS = (
    re.compile(
        r"\b(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2})\s+bullets?\b", re.IGNORECASE
    ),
    re.compile(
        r"\b(?:no\s+more\s+than|maximum\s+of|max(?:imum)?|up\s+to|at\s+most|"
        r"limit(?:ed)?\s+to|keep\s+(?:it\s+|them\s+)?(?:to|under|below)|"
        r"stick\s+to|aim\s+for)\s+(\d{1,2})\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(\d{1,3})\s*(?:words?|w\b)\b", re.IGNORECASE),
    re.compile(r"\b(\d|one|two|1|2)[- ]pages?\b", re.IGNORECASE),
    re.compile(r"\b(?:one[- ]page|two[- ]page|1[- ]page|2[- ]page)\b", re.IGNORECASE),
    re.compile(r"\bword\s+count\b", re.IGNORECASE),
    re.compile(r"\b(?:concise|brief|terse|tight|one[- ]liner)\b", re.IGNORECASE),
)

_TEAM_SIZE_RES = (
    re.compile(r"\bteam\s+of\s+(\d{1,3})\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,3})\s*\+?\s*(?:direct\s+|indirect\s+)?reports\b", re.IGNORECASE),
    re.compile(r"\b(?:managing|leading|overseeing)\s+(?:a\s+)?team\s+of\s+(\d{1,3})\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,3})\s*\+?\s*(?:engineers|developers|people|staff|employees)\b", re.IGNORECASE),
)

_REPORTS_TO_RE = re.compile(
    r"\b(?:reports?\s+to|works?\s+with|under\s+the\s+leadership\s+of|"
    r"in\s+partnership\s+with)\s+((?:the\s+)?[A-Z][\w.-]*(?:\s+[A-Z][\w.-]*){0,2})"
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n{2,}")
_WHITESPACE_RE = re.compile(r"[ \t ]+")
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")

# JSON postings: try these keys (in order) before falling back to a stable dump.
_JSON_TEXT_KEYS = (
    "description",
    "job_description",
    "jobDescription",
    "content",
    "text",
    "body",
    "raw_text",
    "posting",
)


# --- Extraction primitives ---------------------------------------------------


def _slugify(value: str) -> str:
    """Filesystem-safe, deterministic slug. Never returns an empty string."""
    slug = _SLUG_STRIP_RE.sub("_", value.strip().lower()).strip("_")
    return slug[:96]


def _normalize(text: str) -> str:
    """Collapse horizontal whitespace so token counts stay layout-independent."""
    return _WHITESPACE_RE.sub(" ", text.replace("\r\n", "\n").replace("\r", "\n")).strip()


def _ordered_hits(pattern: re.Pattern[str], text: str, limit: int = 12) -> list[str]:
    """Lower-cased, de-duplicated matches in first-appearance order, capped."""
    seen: dict[str, None] = {}
    for match in pattern.finditer(text):
        value = _normalize(match.group(0)).lower()
        if value and value not in seen:
            seen[value] = None
        if len(seen) >= limit:
            break
    return list(seen)


def _extract_tech_tokens(text: str) -> list[str]:
    """Required technical tokens present in the posting (canonical spelling)."""
    found = {m.group(1).lower() for m in _TECH_RE.finditer(text)}
    return sorted(found)


def _extract_degree_certs(text: str) -> list[str]:
    """Degree, certification and credential keywords."""
    return _ordered_hits(_DEGREE_RE, text, limit=10)


def _extract_min_years(text: str) -> int | None:
    """Minimum years of experience demanded, or None when unstated."""
    candidates: list[int] = []
    for low, high in _YEARS_RANGE_RE.findall(text):
        candidates.append(int(low))
        candidates.append(int(high))
    for value in _YEARS_MIN_RE.findall(text):
        candidates.append(int(value))
    viable = [years for years in candidates if 0 < years <= 40]
    return min(viable) if viable else None


def _extract_density_limits(text: str) -> list[str]:
    """Density/verbosity constraints on the candidate's written material."""
    limits: list[str] = []
    seen: set[str] = set()
    for pattern in _DENSITY_PATTERNS:
        # group(0), not findall(): these patterns are grouped, and findall would
        # return bare capture groups ("4-6 bullets" -> "4 6").
        for match in pattern.finditer(text):
            value = _normalize(match.group(0)).lower()
            if value and value not in seen:
                seen.add(value)
                limits.append(value)
    return limits


def _extract_seniority(text: str) -> list[str]:
    """Seniority ladder tokens, capped at the two most senior signals."""
    ordered = []
    seen: set[str] = set()
    for match in _SENIORITY_RE.findall(text):
        value = match.strip().lower()
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered[:2]


def _extract_team_scope(text: str) -> list[str]:
    """Team size / span-of-control signals."""
    scopes: list[str] = []
    seen: set[str] = set()
    for pattern in _TEAM_SIZE_RES:
        for match in pattern.findall(text):
            value = f"team of {match.strip()}"
            if value not in seen:
                seen.add(value)
                scopes.append(value)
    return scopes[:4]


def _extract_chain_of_command(text: str) -> str:
    """First 'reports to X' style leadership anchor, or an empty string."""
    match = _REPORTS_TO_RE.search(text)
    if not match:
        return ""
    return _normalize(match.group(1)).strip(" ,.;:")


def _top_sentence_containing(text: str, vocabulary: tuple[str, ...]) -> str:
    """The first sentence carrying the most vocabulary hits (ties -> earliest)."""
    best_sentence = ""
    best_score = 0
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        cleaned = _normalize(sentence)
        if len(cleaned) < 20:
            continue
        lowered = cleaned.lower()
        score = sum(1 for term in vocabulary if term in lowered)
        if score > best_score:
            best_score = score
            best_sentence = cleaned
    return best_sentence[:280]


def _impact_focus(text: str) -> dict[str, Any]:
    """Domain impact signals plus the single strongest supporting sentence."""
    hits = [term for term in _IMPACT_TENETS if term in text.lower()]
    return {
        "tenets": sorted(set(hits))[:12],
        "evidence": _top_sentence_containing(text, _IMPACT_TENETS),
    }


def _leadership_tenets(text: str) -> dict[str, Any]:
    """Leadership themes present in the posting plus supporting evidence."""
    lowered = text.lower()
    hits = [term for term in _LEADERSHIP_TENETS if term in lowered]
    return {
        "tenets": sorted(set(hits))[:12],
        "evidence": _top_sentence_containing(text, _LEADERSHIP_TENETS),
    }


def _build_persona(
    slug: str,
    title: str,
    company: str,
    seniority: list[str],
    team_scope: list[str],
    chain: str,
) -> dict[str, Any]:
    """Hiring-manager persona overlay merged over the compiled default."""
    role = title.strip() or (seniority[0].title() if seniority else "Target Role")
    if company.strip():
        role = f"{role} @ {company.strip()}"

    perspective_bits = [
        "Pragmatic hiring manager scanning for high-signal proof points",
        f"Targeting {slug}",
    ]
    if team_scope:
        perspective_bits.append(f"Purview: {'; '.join(team_scope)}")
    if chain:
        perspective_bits.append(f"Chain of command: {chain}")

    return {
        "name": f"{role} Hiring Manager",
        "role": role,
        "lens_perspective": " | ".join(perspective_bits),
        "seniority_signals": seniority,
        "team_scope": team_scope,
    }


# --- Rubric construction -----------------------------------------------------


def _tier_0_criteria(tokens: dict[str, Any]) -> list[dict[str, Any]]:
    """Structurally decidable rules: quantified anchors and explicit posting gates.

    Every rule here is checkable by deterministic traversal alone (BKM-015);
    a rule is emitted only when the posting actually states that gate.
    """
    criteria: list[dict[str, Any]] = []

    tech = tokens["technical_tokens"]
    if tech:
        criteria.append(
            {
                "rule_id": "JOB_TECH_TOKEN_COVERAGE",
                "category": "STRUCTURE",
                "target": "role_requirements",
                "severity": "CRITICAL",
                "tier": "tier_0_structural",
                "description": (
                    "The posting names these technical tokens as required evidence; "
                    f"the resume must surface each one: {', '.join(tech)}."
                ),
            }
        )

    degrees = tokens["degree_cert_keywords"]
    if degrees:
        criteria.append(
            {
                "rule_id": "JOB_DEGREE_CERT_GATE",
                "category": "STRUCTURE",
                "target": "education_and_certifications",
                "severity": "HIGH",
                "tier": "tier_0_structural",
                "description": (
                    "Posting gates on these degree/certification keywords: "
                    f"{', '.join(degrees)}. State them explicitly or supply an "
                    "equivalent, verifiable credential."
                ),
            }
        )

    density = tokens["density_limits"]
    if density:
        criteria.append(
            {
                "rule_id": "JOB_DENSITY_LIMIT_CAP",
                "category": "REFINEMENT",
                "target": "section_structure",
                "severity": "MEDIUM",
                "tier": "tier_0_structural",
                "description": (
                    "Posting imposes explicit density/verbosity limits: "
                    f"{', '.join(density)}. Respect them exactly; padding past a "
                    "stated cap is an automatic rejection."
                ),
            }
        )

    min_years = tokens["min_years_experience"]
    if min_years is not None:
        criteria.append(
            {
                "rule_id": "JOB_MIN_YEARS_EXPERIENCE",
                "category": "STRUCTURE",
                "target": "career_timeline",
                "severity": "HIGH",
                "tier": "tier_0_structural",
                "description": (
                    f"Posting requires a minimum of {min_years} years of experience; "
                    "the career timeline must make that tenure legible without "
                    "the reader having to sum the bullets."
                ),
            }
        )

    criteria.append(
        {
            "rule_id": "JOB_QUANTIFIED_PROOF_REQUIRED",
            "category": "REFINEMENT",
            "target": "bone_paragraphs",
            "severity": "HIGH",
            "tier": "tier_0_structural",
            "description": (
                "Every claim answering this posting must carry at least one ASCII "
                "digit anchor (%, count, latency, headcount, budget)."
            ),
        }
    )
    return criteria


def _tier_1_criteria(tokens: dict[str, Any], overflow: list[str]) -> list[dict[str, Any]]:
    """Semantic rules for the LLM judge: persona, impact, leadership."""
    candidates: list[dict[str, Any]] = []

    candidates.append(
        {
            "rule_id": "JOB_HIRING_MANAGER_PERSONA_MATCH",
            "category": "PROSE",
            "target": "summary_section",
            "severity": "HIGH",
            "tier": "tier_1_semantic",
            "description": (
                "Write as if advising the specific hiring manager for this role "
                f"({tokens['title'] or tokens['slug']}). "
                "Read the persona block and match its seniority, purview and "
                "chain of command in tone and emphasis."
            ),
        }
    )

    impact = tokens["impact_focus"]
    if impact["tenets"]:
        candidates.append(
            {
                "rule_id": "JOB_DOMAIN_IMPACT_FOCUS",
                "category": "REFINEMENT",
                "target": "bone_paragraphs",
                "severity": "HIGH",
                "tier": "tier_1_semantic",
                "description": (
                    "This role is scored on domain impact across: "
                    f"{', '.join(impact['tenets'])}. Lead with bullets that move "
                    "those numbers. Posting's own framing: "
                    f"\"{impact['evidence']}\""
                )
                if impact["evidence"]
                else (
                    "This role is scored on domain impact across: "
                    f"{', '.join(impact['tenets'])}. Lead with bullets that move "
                    "those numbers."
                ),
            }
        )

    leadership = tokens["leadership_tenets"]
    if leadership["tenets"]:
        candidates.append(
            {
                "rule_id": "JOB_LEADERSHIP_TENET_EVIDENCE",
                "category": "REFINEMENT",
                "target": "bone_paragraphs",
                "severity": "HIGH",
                "tier": "tier_1_semantic",
                "description": (
                    "The posting asks for these leadership behaviours: "
                    f"{', '.join(leadership['tenets'])}. Each needs a concrete "
                    "proof point naming scope, people moved, and outcome. "
                    f"Posting's own framing: \"{leadership['evidence']}\""
                )
                if leadership["evidence"]
                else (
                    "The posting asks for these leadership behaviours: "
                    f"{', '.join(leadership['tenets'])}. Each needs a concrete "
                    "proof point naming scope, people moved, and outcome."
                ),
            }
        )

    kept = candidates[:_TIER_1_RULE_CAP]
    overflow.extend(rule["rule_id"] for rule in candidates[_TIER_1_RULE_CAP:])
    return kept


def _assert_criteria_sane(criteria: list[dict[str, Any]]) -> None:
    """Fail loudly on any rule craft_lens would reject or silently mis-handle.

    ``_coerce_criteria`` refuses unknown severities/tiers but does *not* police
    ``category``; an invalid category survives coercion and then fails
    ``validate_lens_schema`` inside craft_lens. Catch it here, with the rule_id.
    """
    seen: set[str] = set()
    for rule in criteria:
        rule_id = rule.get("rule_id", "<missing>")
        if rule_id in seen:
            raise ValueError(f"duplicate rule_id in compiled criteria: {rule_id}")
        seen.add(rule_id)
        if rule.get("category") not in CATEGORIES:
            raise ValueError(
                f"rule {rule_id}: category {rule.get('category')!r} not in {CATEGORIES}"
            )
        if rule.get("severity") not in SEVERITIES:
            raise ValueError(
                f"rule {rule_id}: severity {rule.get('severity')!r} not in {SEVERITIES}"
            )
        if rule.get("tier") not in TIERS:
            raise ValueError(f"rule {rule_id}: tier {rule.get('tier')!r} not in {TIERS}")


# --- Public API --------------------------------------------------------------


def extract_job_tokens_and_rubric(job_text: str, slug: str, title: str = "") -> dict[str, Any]:
    """Extract job tokens and compile a valid Lens rubric, fully offline.

    Args:
        job_text: Raw job description. Must be at least ``MIN_CONTENT_CHARS``.
        slug: Identifier for the target role; also seeds the lens title/persona.
        title: Optional human role title (e.g. "Principal Site Reliability Engineer").

    Returns:
        dict with:
            * ``schema``          -- ``"lens.v2"``
            * ``lens_id``         -- ``"job_<slug>"``
            * ``slug``/``title``  -- normalized identity
            * ``tier_0_structural`` -- extracted required tokens, degree/cert
              keywords, density limits, min years (all deterministic)
            * ``tier_1_semantic``  -- hiring manager persona, domain impact focus,
              leadership tenets
            * ``persona``         -- hiring-manager persona overlay
            * ``criteria``        -- rules handed to ``craft_lens``
            * ``overflow``        -- semantic rules dropped by the tier_1 cap
            * ``content_sha256``  -- digest of the normalized posting

    Raises:
        ValueError: on empty/too-short content, a bad slug, or a refusal from
            ``craft_lens``. Never returns a partially-valid rubric.
    """
    if not isinstance(job_text, str):
        raise ValueError(f"job_text must be a string, got {type(job_text).__name__}")

    normalized = _normalize(job_text)
    if len(normalized) < MIN_CONTENT_CHARS:
        raise ValueError(
            f"job description is too short to compile a rubric: {len(normalized)} "
            f"chars (minimum {MIN_CONTENT_CHARS}); refusing to craft from nothing"
        )
    if not isinstance(slug, str) or not slug.strip():
        raise ValueError("slug must be a non-empty string")
    if not isinstance(title, str):
        raise ValueError(f"title must be a str, got {type(title).__name__}")

    slug = _slugify(slug)
    if not slug:
        raise ValueError(f"slug {slug!r} contains no slug-safe characters")

    seniority = _extract_seniority(normalized)
    team_scope = _extract_team_scope(normalized)
    chain = _extract_chain_of_command(normalized)

    tokens: dict[str, Any] = {
        "slug": slug,
        "title": title.strip(),
        "technical_tokens": _extract_tech_tokens(normalized),
        "degree_cert_keywords": _extract_degree_certs(normalized),
        "density_limits": _extract_density_limits(normalized),
        "min_years_experience": _extract_min_years(normalized),
        "seniority": seniority,
        "team_scope": team_scope,
        "chain_of_command": chain,
        "impact_focus": _impact_focus(normalized),
        "leadership_tenets": _leadership_tenets(normalized),
    }

    overflow: list[str] = []
    criteria = _tier_0_criteria(tokens) + _tier_1_criteria(tokens, overflow)
    _assert_criteria_sane(criteria)

    persona = _build_persona(slug, title, "", seniority, team_scope, chain)

    compiled = craft_lens(
        lens_id=f"{JOB_LENS_PREFIX}{slug}",
        content=normalized,
        title=(title.strip() or f"{JOB_LENS_PREFIX}{slug}".replace("_", " ").title()),
        persona=persona,
        criteria=criteria,
    )
    if compiled.get("status") != "success":
        raise ValueError(
            f"craft_lens refused the job rubric for '{slug}': "
            f"{compiled.get('reason', 'unknown reason')}"
        )

    rubric = compiled["rubric"]
    if not validate_lens_schema(rubric):
        raise ValueError(f"compiled rubric for '{slug}' failed its own schema validation")

    return {
        "schema": rubric["schema"],
        "lens_id": rubric["lens_id"],
        "slug": slug,
        "title": title.strip(),
        "tier_0_structural": {
            "technical_tokens": tokens["technical_tokens"],
            "degree_cert_keywords": tokens["degree_cert_keywords"],
            "density_limits": tokens["density_limits"],
            "min_years_experience": tokens["min_years_experience"],
            "seniority_signals": tokens["seniority"],
            "team_scope": tokens["team_scope"],
        },
        "tier_1_semantic": {
            "hiring_manager_persona": persona,
            "domain_impact_focus": tokens["impact_focus"],
            "leadership_tenets": tokens["leadership_tenets"],
        },
        "persona": rubric["persona"],
        "criteria": criteria,
        "overflow": overflow,
        "content_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    }


def _load_source_text(source_path: str) -> str:
    """Read a local posting. ``.json`` is unwrapped via known text keys."""
    path = Path(source_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"job description file not found: {path}")

    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() != ".json":
        return raw

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc

    if isinstance(payload, dict):
        for key in _JSON_TEXT_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        # Stable fallback: key-sorted, ensure_ascii so output is byte-stable.
        return json.dumps(payload, sort_keys=True, ensure_ascii=True)
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def _derive_slug(text: str, title: str, company: str) -> str:
    """Deterministic fallback slug: identity first, content digest last."""
    base = "_".join(part for part in (title, company) if part.strip())
    if base.strip():
        return _slugify(base)
    digest = hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()[:12]
    return f"job_{digest}"


def ingest_job_posting(
    source_path: str = None,
    text: str = None,
    slug: str = None,
    title: str = None,
    company: str = None,
    output_dir: str = None,
    lens_dir: str = None,
) -> tuple[str, str]:
    """Freeze a posting and compile its rubric. Returns (job_path, lens_path).

    Writes ``<output_dir>/<slug>.json`` and ``<lens_dir>/job_<slug>.json``
    atomically (``.tmp`` + ``os.replace``). Requires exactly one of
    ``source_path`` or ``text``. Raises ValueError on a craft refusal rather
    than persisting a half-built artifact.
    """
    if bool(source_path) == bool(text):
        raise ValueError("provide exactly one of source_path or text")
    if text and len(_normalize(text)) < MIN_CONTENT_CHARS:
        raise ValueError(
            f"job description is too short to compile a rubric (minimum "
            f"{MIN_CONTENT_CHARS} chars)"
        )

    job_text = text if text else _load_source_text(source_path)
    resolved_title = (title or "").strip()
    resolved_company = (company or "").strip()
    resolved_slug = _slugify(slug) if slug else _derive_slug(job_text, resolved_title, resolved_company)
    if not resolved_slug:
        raise ValueError("could not derive a slug; pass --slug explicitly")

    payload = extract_job_tokens_and_rubric(job_text, resolved_slug, resolved_title)

    jobs_root = Path(output_dir).expanduser() if output_dir else DEFAULT_JOBS_DIR
    lenses_root = Path(lens_dir).expanduser() if lens_dir else DEFAULT_LENS_DIR
    jobs_root.mkdir(parents=True, exist_ok=True)
    lenses_root.mkdir(parents=True, exist_ok=True)

    # Rebuild the compiled lens through the canonical compiler so the persisted
    # artifact is byte-identical to what craft_lens/persist_lens produce.
    compiled = craft_lens(
        lens_id=f"{JOB_LENS_PREFIX}{resolved_slug}",
        content=_normalize(job_text),
        title=(resolved_title or f"{JOB_LENS_PREFIX}{resolved_slug}".replace("_", " ").title()),
        persona=payload["tier_1_semantic"]["hiring_manager_persona"],
        criteria=payload["criteria"],
    )
    if compiled.get("status") != "success":
        raise ValueError(
            f"craft_lens refused the job rubric for '{resolved_slug}': "
            f"{compiled.get('reason', 'unknown reason')}"
        )

    lens_path = persist_lens(compiled, lenses_root)

    frozen = {
        "schema": "job_posting.v1",
        "slug": resolved_slug,
        "title": resolved_title,
        "company": resolved_company,
        "lens_id": payload["lens_id"],
        "source_path": str(Path(source_path).expanduser()) if source_path else None,
        "content_sha256": payload["content_sha256"],
        "char_count": len(_normalize(job_text)),
        "frozen_posting": _normalize(job_text),
        "tier_0_structural": payload["tier_0_structural"],
        "tier_1_semantic": payload["tier_1_semantic"],
        "criteria": payload["criteria"],
        "criteria_overflow": payload["overflow"],
        "fe_anchors": ["FEAT-622", "BKM-070", "WIS-487"],
    }
    job_path = jobs_root / f"{resolved_slug}.json"
    tmp_path = job_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(frozen, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    os.replace(tmp_path, job_path)

    return str(job_path), str(lens_path)


# --- CLI ---------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m ops.job_ingest",
        description=(
            "Offline job & target ingestion: freeze a raw posting and compile a "
            "deterministic Lens rubric from it. Runs fully offline."
        ),
    )
    parser.add_argument("--file", dest="file_path", default=None, help="Local .txt/.md/.json posting.")
    parser.add_argument("--text", default=None, help="Raw job description text.")
    parser.add_argument("--slug", default=None, help="Identifier/slug for the target role.")
    parser.add_argument("--title", default=None, help="Optional role title.")
    parser.add_argument("--company", default=None, help="Optional company name.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help=f"Target directory for saved job data (default: {DEFAULT_JOBS_DIR}).",
    )
    parser.add_argument(
        "--lens-dir",
        default=None,
        help=f"Target directory for generated lens rubrics (default: {DEFAULT_LENS_DIR}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint. Returns a process exit code; never raises for bad input."""
    args = _build_parser().parse_args(argv)

    if bool(args.file_path) == bool(args.text):
        print("error: provide exactly one of --file or --text", file=sys.stderr)
        return 2

    try:
        job_path, lens_path = ingest_job_posting(
            source_path=args.file_path,
            text=args.text,
            slug=args.slug,
            title=args.title,
            company=args.company,
            output_dir=args.output_dir,
            lens_dir=args.lens_dir,
        )
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"job:  {job_path}")
    print(f"lens: {lens_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

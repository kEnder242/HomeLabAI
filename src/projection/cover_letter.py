#!/usr/bin/env python3
"""
[FEAT-618 / Story 95.10] Live LLM Cover-Letter Synthesis, Grounded in Bone Prose.

The hermetic path -- :meth:`projection.recommender.RecommendationRouter.synthesize_cover_letter`
-- lifts evidence lines verbatim and lets the deterministic assembler frame
them. It is bounded and reproducible, but it cannot connect prose to prose:
the letter reads as an evidence list, not an argument.

This module adds the live pass. The retrieved AST bones and the target job
description are rendered into a structured synthesis prompt and dispatched to
the lab's sovereign engines (:data:`projection.recommender.LIVE_SEAT_LADDER` --
vLLM :8088, M5 Air :8000, Ollama :11434), and the model writes the connective
prose the assembler cannot.

Invariants carried from [FEAT-618] and [BKM-070] section 3:

* **Silicon proposes, the gate disposes.** Model prose is never trusted because
  it reads well. The letter is audited against the shared CP detectors and a
  letter that invents a metric is rejected, not softened.
* **One evidence set.** Grounding comes from
  :meth:`RecommendationRouter.select_grounding_evidence`, the same selector the
  hermetic path uses, so a live pass cannot widen the set of citable claims.
* **Fail closed.** Insufficient grounding never reaches silicon. An offline
  engine raises :class:`~projection.recommender.SiliconUnreachableError`
  instead of silently degrading to the deterministic letter and labelling the
  result a model output.

CP policy for a cover letter is asymmetric, and deliberately so: *dropping*
evidence is acceptable prose behavior, while *inventing* a number is a
fabricated achievement claim. So the hard reject is CP-5 run in reverse
(numeric literals present in the letter but absent from the permitted corpus),
while CP-1 coverage of the evidence is reported as advisory rather than
gating. Both directions are computed by the authoritative
``curator.annotate_resume_spine.verify_containment``, so "numeric" and
"token" keep exactly the definitions the rest of the lab enforces.
"""

from __future__ import annotations

from typing import Any

from .recommender import (
    LIVE_JUDGE_TEMPERATURE,
    RecommendationRouter,
    SiliconUnreachableError,
    acomplete_live_traced,
    build_gate_document,
    complete_live_traced,
    load_shared_detectors,
)

__all__ = [
    "COVER_LETTER_SYSTEM_DIRECTIVE",
    "CoverLetterSynthesizer",
    "SiliconUnreachableError",
]

#: The non-negotiable grounding directive handed to the model as its system
#: prompt. It is fixed text rather than a template parameter because relaxing
#: it is a *policy* change, not a per-request preference: the permitted claim
#: set is the bones, and the model does not get to expand it.
COVER_LETTER_SYSTEM_DIRECTIVE = (
    "You write cover letters for a senior engineer whose career evidence is "
    "frozen and certified. You may use ONLY the EVIDENCE lines provided: every "
    "claim, metric, employer, and technology must trace to one of them or to "
    "the TARGET ROLE description. Never invent an achievement, a number, a "
    "percentage, a team size, a citation, or a tool. Never assert a skill the "
    "evidence does not support. Connect the evidence into a persuasive letter "
    "aimed at the target role. Return the letter prose only: no preamble, no "
    "commentary about the evidence, no markdown fences."
)


class CoverLetterSynthesizer:
    """Grounded live cover-letter synthesis.

    Composes three already-authoritative pieces rather than reimplementing any
    of them: the evidence selector and alignment matrix from
    :class:`~projection.recommender.RecommendationRouter`, the engine seam from
    :mod:`projection.recommender`, and the CP detectors from the ``curator``
    package.
    """

    def __init__(self, router: RecommendationRouter | None = None) -> None:
        self.router = router or RecommendationRouter()

    # -- grounding ---------------------------------------------------------

    def ground(self, bones, job_desc: str, limit: int | None = None) -> dict[str, Any]:
        """Select the citable evidence for a job description.

        Thin pass-through to the shared selector, kept as a method so callers
        can inspect the claim set before spending a live completion on it.
        """
        return self.router.select_grounding_evidence(bones, job_desc, limit=limit)

    def _fallback_letter(self, bones, job_desc: str) -> str:
        """The deterministic, already-verified letter.

        Used as the refusal payload when silicon is unreachable or when the
        model fabricates a metric. It is the letter the hermetic path would
        have produced, so a refused live pass degrades to *known-good* prose
        rather than to nothing.
        """
        return self.router.synthesize_cover_letter(bones, job_desc)

    # -- prompt ------------------------------------------------------------

    @staticmethod
    def build_prompt(job_desc: str, grounding: dict[str, Any]) -> str:
        """Render the structured synthesis prompt from evidence and target role.

        The evidence lines are labeled and numbered so the model can attribute
        each claim, and both blocks are always present even when empty -- a
        silently dropped block is how a model ends up writing a generic letter
        that no longer traces to the bones.
        """
        evidence = grounding.get("evidence") or []
        job_text = str(job_desc or "").strip() or "(no job description supplied)"

        lines = [
            f"TARGET ROLE ({len(evidence)} certified evidence line(s) available):",
            job_text,
            "",
            "EVIDENCE (the only claims you may make):",
        ]
        if evidence:
            for index, item in enumerate(evidence, start=1):
                lines.append(f"E{index} [bone: {item.get('bone_id', 'unknown')}]: {item.get('text', '')}")
        else:
            lines.append("(none)")
        lines += [
            "",
            "Write a cover letter that argues this candidate fits the target",
            "role using only the numbered evidence above. Return prose only.",
        ]
        return "\n".join(lines)

    # -- grounding gate ----------------------------------------------------

    @staticmethod
    def audit_grounding(letter: str, grounding: dict[str, Any], job_desc: str) -> dict[str, Any]:
        """Audit model prose against the permitted claim set.

        Two directions, one shared detector:

        * **CP-5 reverse (hard reject).** Literals present in the letter but
          absent from evidence + job description are *fabricated metrics*.
          ``verify_containment(letter, permitted)`` reports exactly those as
          ``lost_literals``, so the authoritative numeric definition decides
          what counts as invented -- no local regex.
        * **CP-1 forward (advisory).** Evidence tokens the letter never used.
          A letter may legitimately compress evidence, so this is reported to
          the operator instead of gating.
        """
        detectors = load_shared_detectors()
        evidence = grounding.get("evidence") or []
        evidence_text = " ".join(str(item.get("text", "")) for item in evidence)
        permitted_text = f"{evidence_text} {job_desc}".strip()

        if detectors is None:
            return {
                "verdict": "UNVERIFIED",
                "passed": False,
                "reason": (
                    "curator.validate_paper_schema / curator.annotate_resume_spine "
                    "are unreachable; refusing to certify a model-written letter "
                    "against a gate that could not be loaded."
                ),
                "fabricated_literals": [],
                "unaddressed_evidence_tokens": [],
            }

        _validate_paper_ast, verify_containment = detectors

        letter_doc = build_gate_document("cover_letter", letter, paper_id="cover_letter")
        permitted_doc = build_gate_document(
            "cover_letter", permitted_text, paper_id="cover_letter", revision_id="permitted"
        )

        fabrication = verify_containment(letter_doc, permitted_doc)["cp5_numeric_literals"]
        coverage = verify_containment(permitted_doc, letter_doc)["cp1_token_containment"]

        fabricated = sorted(
            {
                literal
                for violation in fabrication["violations"]
                for literal in violation.get("lost_literals", [])
            }
        )
        unaddressed = sorted(
            {
                token
                for violation in coverage["violations"]
                for token in violation.get("lost_tokens", [])
            }
        )
        return {
            "verdict": "PASS" if not fabricated else "FAIL",
            "passed": not fabricated,
            "fabricated_literals": fabricated,
            "unaddressed_evidence_tokens": unaddressed,
            "evidence_lines_cited": len(evidence),
        }

    # -- synthesis ---------------------------------------------------------

    def _result(
        self,
        status: str,
        letter: str,
        grounding: dict[str, Any],
        audit: dict[str, Any],
        silicon: dict[str, Any] | None,
        reason: str = "",
    ) -> dict[str, Any]:
        """Assemble the JSON-serializable synthesis report."""
        result: dict[str, Any] = {
            "status": status,
            "feature": "FEAT-618",
            "letter": letter,
            "letter_source": "live_llm" if status == "success" else "deterministic",
            "grounding": {
                "evidence": grounding.get("evidence", []),
                "covered_requirements": grounding.get("covered", []),
                "requirement_count": len(grounding.get("job_tokens", [])),
                "mean_alignment": grounding.get("overall", 0.0),
            },
            "grounding_audit": audit,
        }
        if silicon is not None:
            result["silicon"] = silicon
        if reason:
            result["reason"] = reason
        return result

    def _insufficient(self, grounding: dict[str, Any], bones, job_desc: str) -> dict[str, Any]:
        """Fail closed before silicon: no evidence, no completion is attempted."""
        return self._result(
            "insufficient_grounding",
            self._fallback_letter(bones, job_desc),
            grounding,
            {"verdict": "UNVERIFIED", "passed": False, "reason": "not adjudicated: no evidence to ground a letter in"},
            None,
            reason=str(grounding.get("reason", "")),
        )

    def synthesize_live(
        self,
        bones,
        job_desc: str,
        *,
        limit: int | None = None,
        live_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Synthesize a cover letter with live silicon, grounded in bone prose.

        Raises :class:`~projection.recommender.SiliconUnreachableError` when no
        engine seat answers -- an offline lab is an explicit error, never a
        deterministic letter wearing a model's name. Returns a report whose
        ``status`` is ``insufficient_grounding``, ``rejected`` (the model
        fabricated a metric) or ``success``.
        """
        grounding = self.ground(bones, job_desc, limit=limit)
        if grounding["status"] != "success":
            return self._insufficient(grounding, bones, job_desc)

        options = dict(live_options or {})
        options.setdefault("temperature", LIVE_JUDGE_TEMPERATURE)
        letter, silicon = complete_live_traced(
            self.build_prompt(job_desc, grounding),
            COVER_LETTER_SYSTEM_DIRECTIVE,
            **options,
        )

        audit = self.audit_grounding(letter, grounding, job_desc)
        if not audit["passed"]:
            # A model-written letter that invents a metric is a lie with a
            # citation. Ship the deterministic letter and report the breach.
            return self._result(
                "rejected",
                self._fallback_letter(bones, job_desc),
                grounding,
                audit,
                silicon,
                reason=(
                    "live letter failed the CP-5 grounding gate "
                    f"(fabricated literal(s): {', '.join(audit['fabricated_literals']) or 'unknown'}); "
                    "the deterministic letter was returned instead"
                ),
            )

        return self._result("success", letter, grounding, audit, silicon)

    async def asynthesize_live(
        self,
        bones,
        job_desc: str,
        *,
        limit: int | None = None,
        live_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Async twin of :meth:`synthesize_live`.

        The shared engine client offloads its blocking request to an executor,
        so a cold engine cannot stall the Foyer event loop.
        """
        grounding = self.ground(bones, job_desc, limit=limit)
        if grounding["status"] != "success":
            return self._insufficient(grounding, bones, job_desc)

        options = dict(live_options or {})
        options.setdefault("temperature", LIVE_JUDGE_TEMPERATURE)
        letter, silicon = await acomplete_live_traced(
            self.build_prompt(job_desc, grounding),
            COVER_LETTER_SYSTEM_DIRECTIVE,
            **options,
        )

        audit = self.audit_grounding(letter, grounding, job_desc)
        if not audit["passed"]:
            return self._result(
                "rejected",
                self._fallback_letter(bones, job_desc),
                grounding,
                audit,
                silicon,
                reason=(
                    "live letter failed the CP-5 grounding gate "
                    f"(fabricated literal(s): {', '.join(audit['fabricated_literals']) or 'unknown'}); "
                    "the deterministic letter was returned instead"
                ),
            )

        return self._result("success", letter, grounding, audit, silicon)

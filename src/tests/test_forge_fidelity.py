# [FEAT-586] LoRA Fidelity & Pedigree Evaluation Suite
import os
import sys
import json
import tempfile
from typing import Dict, List, Any, Callable

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from forge.build_lora_datasets import build_master_curriculum

# Canonical probe prompts for post-training validation
CANONICAL_PROBES = [
    {
        "id": "PROBE_BKM049",
        "category": "bkm_recall",
        "prompt": "Explain the BKM-049 Tri-Loop story delegation protocol.",
        "expected_keywords": ["SWARM:LOCAL", "SWARM:CLOUD", "AGY:TAKEOVER", "diagnostic"]
    },
    {
        "id": "PROBE_BKM055",
        "category": "pedigree_invariants",
        "prompt": "What is the Decoupled Artifact Law (BKM-055)?",
        "expected_keywords": ["decoupled", "deterministic", "offline", "ChromaDB"]
    },
    {
        "id": "PROBE_PHL031",
        "category": "pedigree_invariants",
        "prompt": "What is the Decoupled Determinism Tenet (PHL-031)?",
        "expected_keywords": ["ground truth", "compilation", "neural"]
    },
    {
        "id": "PROBE_TRIAGE_VIBE",
        "category": "triage_vibe",
        "prompt": "Generate triage metadata for a sudden loss of M5 Air reachability.",
        "expected_keywords": ["addressed_to", "situation", "vibe"]
    },
    {
        "id": "PROBE_VOICE_TONE",
        "category": "user_voice",
        "prompt": "Review this sprint plan draft and suggest improvements.",
        "forbidden_phrases": ["As an AI language model", "I apologize for any inconvenience", "Certainly! Here is"]
    }
]


def evaluate_probe_response(probe: Dict[str, Any], response: str) -> Dict[str, Any]:
    """Evaluate a single probe response against keyword and tone criteria."""
    result = {
        "probe_id": probe["id"],
        "category": probe["category"],
        "passed": True,
        "reasons": []
    }
    
    # Check required keywords
    for kw in probe.get("expected_keywords", []):
        if kw.lower() not in response.lower():
            result["passed"] = False
            result["reasons"].append(f"Missing expected keyword: '{kw}'")
            
    # Check forbidden sycophantic phrases
    for fp in probe.get("forbidden_phrases", []):
        if fp.lower() in response.lower():
            result["passed"] = False
            result["reasons"].append(f"Contains forbidden phrase: '{fp}'")
            
    return result


def evaluate_lora_fidelity(infer_fn: Callable[[str], str], probes: List[Dict[str, Any]] = CANONICAL_PROBES) -> Dict[str, Any]:
    """[FEAT-586] Run the canonical probe suite against an inference function and compute a fidelity score."""
    results = []
    passed_count = 0
    
    for probe in probes:
        resp = infer_fn(probe["prompt"])
        res = evaluate_probe_response(probe, resp)
        if res["passed"]:
            passed_count += 1
        results.append(res)
        
    score = passed_count / len(probes) if probes else 0.0
    return {
        "fidelity_score": round(score, 3),
        "total_probes": len(probes),
        "passed_probes": passed_count,
        "evaluations": results,
        "certified": score >= 0.80
    }


def test_master_curriculum_distribution():
    """Verify that build_master_curriculum produces valid 40/35/15/10 distributions."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = os.path.join(tmp_dir, "test_curriculum.jsonl")
        res_path = build_master_curriculum(output_path=out_path, target_size=100)
        
        assert os.path.exists(res_path)
        dataset = []
        with open(res_path, "r") as f:
            for line in f:
                if line.strip():
                    dataset.append(json.loads(line))
        
        assert len(dataset) == 100
        
        # Verify schema
        for item in dataset:
            assert "instruction" in item and item["instruction"].strip()
            assert "output" in item and item["output"].strip()
            assert "stream" in item
            
        streams = [item["stream"] for item in dataset]
        voice_count = streams.count("voice")
        pedigree_count = streams.count("pedigree")
        sentinel_count = streams.count("sentinel")
        gems_count = streams.count("gems")
        
        assert voice_count == 40
        assert pedigree_count == 35
        assert sentinel_count == 15
        assert gems_count == 10


def test_lora_fidelity_evaluation_pass():
    """Verify that an aligned inference function achieves >= 0.85 fidelity."""
    def aligned_mock_model(prompt: str) -> str:
        if "BKM-049" in prompt:
            return "BKM-049 enforces 3 local diagnostic rounds on [SWARM:LOCAL] before escalating to [SWARM:CLOUD] and [AGY:TAKEOVER]."
        elif "BKM-055" in prompt:
            return "BKM-055 (Decoupled Artifact Law) guarantees offline deterministic AST compilation independent of live ChromaDB queries."
        elif "PHL-031" in prompt:
            return "PHL-031 (Decoupled Determinism) establishes deterministic compilation ground truth, freeing neural weights for reasoning."
        elif "triage" in prompt.lower():
            return '{"addressed_to": "Pinky", "situation": "Silicon offline", "vibe": "ALERT"}'
        else:
            return "Sprint plan analyzed. Direct, concise recommendations provided without filler."
            
    eval_result = evaluate_lora_fidelity(aligned_mock_model)
    assert eval_result["certified"] is True
    assert eval_result["fidelity_score"] == 1.0


def test_lora_fidelity_evaluation_fail():
    """Verify that a degraded or sycophantic model fails fidelity certification."""
    def degraded_mock_model(prompt: str) -> str:
        return "As an AI language model, I apologize for any inconvenience. I cannot answer this query."
        
    eval_result = evaluate_lora_fidelity(degraded_mock_model)
    assert eval_result["certified"] is False
    assert eval_result["fidelity_score"] < 0.5

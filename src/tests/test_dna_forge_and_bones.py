import json
from pathlib import Path
from nodes.pinky_critic_persona import (
    CriticResult,
    parse_critic_payload
)

PORTFOLIO_DIR = Path(__file__).resolve().parent.parent.parent.parent / "Portfolio_Dev" / "field_notes"
BONES_PATH = PORTFOLIO_DIR / "data" / "bone_collections.json"
MANIFEST_PATH = PORTFOLIO_DIR / "data" / "dna_manifest.json"


def test_dna_proposal_dataclass_and_parsing():
    raw_json = json.dumps({
        "cartoon_retort": "Egads! What a marvelous insight!",
        "critique_suggestions": ["Ensure anchor links are preserved."],
        "score": 5,
        "dna_proposal": {
            "id": "BKM-099",
            "domain": "BKM",
            "title": "Always Validate REST Before Re-bucketing",
            "summary": "Mandatory REST pre-flight probe.",
            "rationale": "Prevents data corruption across distributed nodes.",
            "tags": ["validation", "rest", "bkm"]
        }
    })
    
    result = parse_critic_payload(raw_json)
    assert isinstance(result, CriticResult)
    assert result.score == 5
    assert result.dna_proposal is not None
    assert result.dna_proposal.id == "BKM-099"
    assert result.dna_proposal.domain == "BKM"
    assert "validation" in result.dna_proposal.tags
    assert result.dna_proposal.status == "PROPOSED"


def test_critic_payload_embedded_json_with_dna_proposal():
    embedded_raw = """
    Here is our synthesized conclusion:
    ```json
    {
      "retort": "Narf! We caught another edge case!",
      "score": 4,
      "dna_proposal": {
        "id": "WIS-050",
        "domain": "WIS",
        "title": "The Ghost in the Packet Buffer",
        "summary": "Serial line clipping caused silent drop."
      }
    }
    ```
    Good luck!
    """
    result = parse_critic_payload(embedded_raw)
    assert result.score == 4
    assert result.dna_proposal is not None
    assert result.dna_proposal.id == "WIS-050"
    assert result.dna_proposal.domain == "WIS"


def test_bone_collections_schema_and_manifest():
    assert BONES_PATH.exists(), f"Missing bone_collections.json at {BONES_PATH}"
    with open(BONES_PATH, "r", encoding="utf-8") as f:
        collections = json.load(f)
    
    assert isinstance(collections, list)
    assert len(collections) >= 2
    
    # Verify core scaffold structure
    core = next((c for c in collections if c.get("id") == "bone_core_scaffold"), None)
    assert core is not None
    assert len(core.get("bones", [])) >= 4
    for bone in core["bones"]:
        assert "id" in bone
        assert "domain" in bone
        assert "title" in bone


def test_dna_manifest_polymorphic_domains():
    assert MANIFEST_PATH.exists(), f"Missing dna_manifest.json at {MANIFEST_PATH}"
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    
    expected_domains = ["philosophy", "wisdom", "rdna", "discovery", "feature", "behavioral", "sprint"]
    for d in expected_domains:
        assert d in manifest, f"Expected domain {d} in manifest"
        assert len(manifest[d]) > 0, f"Domain {d} should have cards loaded"

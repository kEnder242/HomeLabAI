import asyncio
import os
import json
import pytest
from recruiter import NightlyRecruiter

@pytest.mark.asyncio
async def test_scoring_logic():
    """Verifies Multi-Vector scoring and Local Multipliers."""
    recruiter = NightlyRecruiter()
    
    # Pillar 1: Telemetry
    job_telemetry = {
        "title": "Telemetry Engineer",
        "description": "Expert in RAPL and MSR profiling."
    }
    score_1 = await recruiter.calculate_match_score(job_telemetry)
    assert score_1 >= 0.2
    
    # Multi-Pillar: Telemetry + Manageability
    job_unicorn = {
        "title": "Manageability Architect",
        "description": "Expert in RAPL, Redfish, and OpenBMC."
    }
    score_2 = await recruiter.calculate_match_score(job_unicorn)
    # Should be significantly higher due to exponential boost
    assert score_2 > score_1
    
    # Local Boost: Hillsboro
    job_local = {
        "title": "Software Engineer",
        "description": "Python validation role in Hillsboro, OR."
    }
    score_3 = await recruiter.calculate_match_score(job_local)
    assert score_3 > 0.2 # Base for Python + Local multiplier

@pytest.mark.asyncio
async def test_deduplication():
    """Verifies that the ledger prevents redundant processing."""
    recruiter = NightlyRecruiter()
    job = {"url": "https://test.com/job1", "title": "Test", "company": "Test"}
    
    # Clear ledger for test
    if os.path.exists(recruiter.ledger_path):
        os.remove(recruiter.ledger_path)
    
    assert recruiter.is_duplicate(job) is False
    recruiter.mark_as_processed(job)
    assert recruiter.is_duplicate(job) is True

if __name__ == "__main__":
    # Standard Python execution for quick shakedown
    async def run_all():
        print("[TEST] Starting Recruiter Shakedown...")
        await test_scoring_logic()
        print("[PASS] Scoring Logic Verified.")
        await test_deduplication()
        print("[PASS] Deduplication Verified.")
        
    asyncio.run(run_all())

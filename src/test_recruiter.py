import asyncio
import os
import pytest
import recruiter

@pytest.mark.asyncio
async def test_recruiter_brief_generation():
    """Verifies that the Recruiter can generate a markdown brief."""

    # Mock the Recruiter to avoid real searches/archive calls
    r = recruiter.NightlyRecruiter()

    # Inject mock data
    jobs = [
        {"title": "Test Engineer", "company": "Acme Corp", "url": "http://example.com"}
    ]
    context = "Validation Expert."

    # Run generation
    path = await r.generate_brief(jobs, context)

    # Verify file existence and content
    assert os.path.exists(path)
    with open(path, "r") as f:
        content = f.read()
        assert "Nightly Recruiter Brief" in content
        assert "Acme Corp" in content

    # Cleanup
    os.remove(path)
    print("[PASS] Recruiter Brief Generation Verified.")

if __name__ == "__main__":
    asyncio.run(test_recruiter_brief_generation())

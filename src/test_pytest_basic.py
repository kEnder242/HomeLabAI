import pytest
import asyncio

def test_example_assertion():
    assert 1 + 1 == 2

@pytest.mark.asyncio
async def test_example_async_assertion():
    await asyncio.sleep(0.01) # Simulate async work
    assert True

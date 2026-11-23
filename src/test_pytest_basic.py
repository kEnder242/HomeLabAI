# Copyright 2025-2026 Jason Allred
# SPDX-License-Identifier: Apache-2.0
import asyncio

import pytest


def test_example_assertion():
    assert 1 + 1 == 2


@pytest.mark.asyncio
async def test_example_async_assertion():
    await asyncio.sleep(0.01)  # Simulate async work
    assert True

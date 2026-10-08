"""Tests for in-memory TTL cache used by *arr clients."""

import asyncio

import pytest

from app.services.arr_cache import TTLCache


@pytest.mark.asyncio
async def test_cache_miss_then_hit():
    cache = TTLCache()
    calls = 0

    async def factory():
        nonlocal calls
        calls += 1
        return {"n": calls}

    first = await cache.get_or_set("k", 60.0, factory)
    second = await cache.get_or_set("k", 60.0, factory)
    assert first == {"n": 1}
    assert second == {"n": 1}
    assert calls == 1
    assert len(cache) == 1


@pytest.mark.asyncio
async def test_cache_expiry():
    cache = TTLCache()
    calls = 0

    async def factory():
        nonlocal calls
        calls += 1
        return calls

    await cache.get_or_set("k", 0.01, factory)
    await asyncio.sleep(0.02)
    value = await cache.get_or_set("k", 0.01, factory)
    assert value == 2
    assert calls == 2


@pytest.mark.asyncio
async def test_invalidate_prefix():
    cache = TTLCache()

    async def factory():
        return "x"

    await cache.get_or_set("arr:series:list", 60.0, factory)
    await cache.get_or_set("arr:series:1", 60.0, factory)
    await cache.get_or_set("arr:movies:list", 60.0, factory)

    cache.invalidate("arr:series:")
    assert len(cache) == 1

    cache.invalidate()
    assert len(cache) == 0

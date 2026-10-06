"""retry_async 装饰器单元测试：验证重试次数、退避与异常分类。"""

import asyncio

import pytest

from tools import retry_async


class TestRetryAsync:
    def test_success_first_try(self):
        """首次成功不应重试。"""
        calls = []

        @retry_async(max_attempts=3)
        async def fn():
            calls.append(1)
            return "ok"

        assert asyncio.run(fn()) == "ok"
        assert len(calls) == 1

    def test_retries_then_succeeds(self):
        """失败后重试，最终成功。"""
        calls = []

        @retry_async(max_attempts=3, base_delay=0.01)
        async def fn():
            calls.append(1)
            if len(calls) < 3:
                raise ConnectionError("network down")
            return "recovered"

        assert asyncio.run(fn()) == "recovered"
        assert len(calls) == 3

    def test_gives_up_after_max_attempts(self):
        """超过最大次数后抛出原始异常。"""
        calls = []

        @retry_async(max_attempts=2, base_delay=0.01)
        async def fn():
            calls.append(1)
            raise ConnectionError("always fail")

        with pytest.raises(ConnectionError):
            asyncio.run(fn())
        assert len(calls) == 2

    def test_non_retryable_exception_raises_immediately(self):
        """非重试类异常（如 ValueError）应立即抛出，不重试。"""
        calls = []

        @retry_async(max_attempts=3, base_delay=0.01)
        async def fn():
            calls.append(1)
            raise ValueError("business error")

        with pytest.raises(ValueError):
            asyncio.run(fn())
        assert len(calls) == 1

    def test_custom_retryable_exceptions(self):
        """自定义重试异常元组应生效。"""
        calls = []

        @retry_async(max_attempts=3, base_delay=0.01,
                     retryable_exceptions=(ValueError,))
        async def fn():
            calls.append(1)
            if len(calls) < 2:
                raise ValueError("transient value error")
            return "done"

        assert asyncio.run(fn()) == "done"
        assert len(calls) == 2

    def test_exponential_backoff_increases(self, monkeypatch):
        """退避延迟应按指数增长（1s, 2s, 4s...）。"""
        delays = []

        async def fake_sleep(secs):
            delays.append(secs)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)

        calls = []

        @retry_async(max_attempts=4, base_delay=1.0, max_delay=8.0)
        async def fn():
            calls.append(1)
            if len(calls) < 4:
                raise ConnectionError("x")
            return "ok"

        assert asyncio.run(fn()) == "ok"
        assert delays[0] == 1.0
        assert delays[1] == 2.0
        assert delays[2] == 4.0

    def test_delay_capped_at_max(self, monkeypatch):
        """退避延迟不应超过 max_delay。"""
        delays = []

        async def fake_sleep(secs):
            delays.append(secs)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)

        calls = []

        @retry_async(max_attempts=5, base_delay=2.0, max_delay=5.0)
        async def fn():
            calls.append(1)
            if len(calls) < 5:
                raise ConnectionError("x")
            return "ok"

        assert asyncio.run(fn()) == "ok"
        assert delays == [2.0, 4.0, 5.0, 5.0]

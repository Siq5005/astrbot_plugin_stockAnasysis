"""通用 OpenAI 兼容 LLM 适配器。"""

from __future__ import annotations

import asyncio
import re

import aiohttp

from astrbot.api import logger

# 可重试的 HTTP 状态码
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class OpenAICompatibleLLM:
    """适配 OpenAI Chat Completions 协议的异步 LLM 客户端。"""

    def __init__(
        self,
        api_key: str,
        api_base: str,
        model: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        timeout_seconds: int = 120,
        reasoning: bool | None = None,
        max_retries: int = 2,
    ):
        self.url = api_base.rstrip("/") + "/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        }
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.reasoning = reasoning
        self.max_retries = max_retries
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建复用的 aiohttp 会话。"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """关闭底层连接池，应在插件卸载时调用。"""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    async def ask(self, prompt: str) -> str:
        return await self.__call__(prompt)

    async def __call__(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        if self.reasoning is not None:
            payload["reasoning"] = self.reasoning

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                session = await self._get_session()
                async with session.post(
                    self.url, headers=self.headers, json=payload
                ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            if response.status in _RETRYABLE_STATUS and attempt < self.max_retries:
                                wait = 2 ** attempt
                                logger.warning(
                                    "LLM API 返回 %d (尝试 %d/%d)，%ds 后重试…",
                                    response.status, attempt + 1, self.max_retries + 1, wait,
                                )
                                await asyncio.sleep(wait)
                                continue
                            raise RuntimeError(
                                f"LLM API错误 ({response.status}): {error_text[:300]}"
                            )

                        result = await response.json()
                        content = result["choices"][0]["message"]["content"]
                        return self._clean_response(content)

            except asyncio.TimeoutError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.warning(
                        "LLM 超时 (尝试 %d/%d, 超时 %ds)，%ds 后重试…",
                        attempt + 1, self.max_retries + 1, self.timeout_seconds, wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                break

            except aiohttp.ClientError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.warning(
                        "LLM 网络错误 (尝试 %d/%d): %s，%ds 后重试…",
                        attempt + 1, self.max_retries + 1, exc, wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                break

        raise RuntimeError(
            f"LLM 调用失败（已重试 {self.max_retries} 次）: {type(last_error).__name__}: {last_error}"
        ) from last_error

    @staticmethod
    def _clean_response(content: str) -> str:
        if not content:
            return content
        cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE)
        return cleaned.strip() or content.strip()
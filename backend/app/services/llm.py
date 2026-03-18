from __future__ import annotations
import asyncio
import json
import logging
import re
import time

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, api_key: str, base_url: str, model: str, max_concurrent: int = 10):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.total_tokens = 0
        self.total_calls = 0
        self._lock = asyncio.Lock()

    async def _track(self, usage):
        if usage:
            async with self._lock:
                self.total_tokens += usage.total_tokens or 0
                self.total_calls += 1

    async def generate(
        self,
        system: str,
        user: str,
        json_mode: bool = False,
        max_tokens: int = 1000,
        retries: int = 3,
    ) -> str:
        kwargs: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.8,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        for attempt in range(retries):
            try:
                async with self.semaphore:
                    response = await self.client.chat.completions.create(**kwargs)
                await self._track(response.usage)
                content = response.choices[0].message.content or ""
                return content.strip()
            except Exception as e:
                if attempt == retries - 1:
                    logger.error("LLM call failed after %d retries: %s", retries, e)
                    raise
                wait = 2 ** attempt
                logger.warning("LLM call failed (attempt %d), retrying in %ds: %s", attempt + 1, wait, e)
                await asyncio.sleep(wait)
        return ""

    async def generate_batch(
        self,
        prompts: list[tuple[str, str]],
        json_mode: bool = False,
        max_tokens: int = 1000,
    ) -> list[str]:
        tasks = [self.generate(system, user, json_mode=json_mode, max_tokens=max_tokens) for system, user in prompts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r if isinstance(r, str) else "" for r in results]

    async def generate_light(self, system: str, user: str, max_tokens: int = 100) -> str:
        return await self.generate(system, user, json_mode=False, max_tokens=max_tokens)

    def get_stats(self) -> dict:
        return {
            "total_tokens": self.total_tokens,
            "total_calls": self.total_calls,
        }


def parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for i in range(len(text) - 1, -1, -1):
        if text[i] in "]}":
            try:
                return json.loads(text[: i + 1])
            except json.JSONDecodeError:
                continue

    open_braces = text.count("{") - text.count("}")
    open_brackets = text.count("[") - text.count("]")
    repaired = text + ("}" * max(0, open_braces)) + ("]" * max(0, open_brackets))
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    logger.error("Failed to parse JSON from LLM response: %s...", text[:200])
    return {}

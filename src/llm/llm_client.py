"""LLM 客户端模块：封装 OpenAI 兼容 API 调用。

特点：
  - 支持任意 OpenAI 兼容的 API 端点（OpenAI、阿里云 DashScope、本地部署等）
  - 双轨 HTTP：requests（优先）→ urllib（fallback）
  - API key 不可用时自动降级为 [fallback] 前缀文本
  - 调用失败不抛异常，返回 fallback 以保证 Pipeline 不中断
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

try:
    import requests
except ImportError:  # pragma: no cover - optional dependency path
    requests = None

LOGGER = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM 连接配置。"""
    provider: str = "openai_compatible"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    timeout: int = 60


class LLMClient:
    """OpenAI 兼容协议的大模型客户端，支持优雅降级。"""
    FALLBACK_PREFIX = "[fallback]"

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def complete(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful AI assistant.",
        temperature: float = 0.3,
        max_tokens: int = 600,
    ) -> str:
        """调用 LLM 完成请求，失败或无 API key 时自动降级为 fallback。"""
        if not self.config.api_key:
            return self._fallback(prompt)

        try:
            response = self._call_openai_compatible(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = self._extract_content(response)
            return content or self._fallback(prompt)
        except Exception as exc:
            LOGGER.warning("LLM call failed, fallback enabled: %s", exc)
            return self._fallback(prompt)

    def _call_openai_compatible(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        endpoint = urljoin(self.config.base_url.rstrip("/") + "/", "chat/completions")
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self._uses_dashscope_compat():
            payload["enable_thinking"] = False

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        if requests is not None:
            try:
                response = requests.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.config.timeout,
                )
                response.raise_for_status()
                return response.json()
            except requests.HTTPError as exc:
                detail = ""
                if exc.response is not None:
                    detail = exc.response.text.strip()
                raise RuntimeError(
                    f"HTTP error from {endpoint}: {detail or exc}"
                ) from exc

        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.config.timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore").strip()
            raise RuntimeError(
                f"HTTP error from {endpoint}: {detail or exc.reason}"
            ) from exc

    def _uses_dashscope_compat(self) -> bool:
        base_url = self.config.base_url.lower()
        provider = self.config.provider.lower()
        return "dashscope" in base_url or provider == "dashscope"

    @classmethod
    def is_fallback_response(cls, text: str) -> bool:
        """判断是否为降级响应，供调用方决定是否使用备用逻辑。"""
        return text.strip().startswith(cls.FALLBACK_PREFIX)

    @staticmethod
    def _extract_content(response: dict) -> str:
        message = response.get("choices", [{}])[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, list):
            text_fragments = []
            for part in content:
                if isinstance(part, dict):
                    text_fragments.append(str(part.get("text", "")))
                else:
                    text_fragments.append(str(part))
            return "".join(text_fragments).strip()
        return str(content).strip()

    @classmethod
    def _fallback(cls, prompt: str) -> str:
        text = " ".join((prompt or "").split())
        if not text:
            return "No content available."
        if len(text) > 180:
            text = text[:180] + "..."
        return f"{cls.FALLBACK_PREFIX} {text}"

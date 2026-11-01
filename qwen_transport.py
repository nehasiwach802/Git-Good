"""Optional Qwen wording client using Model Studio's compatible chat API."""

import os
from urllib.parse import urlsplit


class QwenTransport:
    def __init__(self, base_url: str, api_key: str, model: str, *, timeout: float = 20):
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Qwen base URL must be HTTPS without embedded credentials")
        if not api_key or not model or timeout <= 0:
            raise ValueError("Qwen API key, model, and positive timeout are required")
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._key = api_key
        self._model = model
        self._timeout = timeout

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("QWEN_BASE_URL", ""),
                   os.environ.get("DASHSCOPE_API_KEY", ""),
                   os.environ.get("QWEN_MODEL", ""))

    def __call__(self, messages: list[dict]) -> str:
        import httpx
        try:
            response = httpx.post(self._url, headers={"Authorization": f"Bearer {self._key}"},
                                  json={"model": self._model, "messages": messages,
                                        "stream": False}, timeout=self._timeout)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception:
            raise RuntimeError("Qwen wording request failed") from None

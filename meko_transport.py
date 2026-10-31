"""Opt-in authenticated Streamable HTTP transport using the official MCP SDK.

Importing this module never connects. Credentials come from the backend environment.
Use this synchronous transport in synchronous code or an async server's worker thread.
"""

import asyncio
import math
import os
from urllib.parse import urlsplit

from lab_memory import MemoryServiceError


class MekoTransport:
    def __init__(self, endpoint: str, token: str, timeout: float = 30):
        parsed = urlsplit(endpoint)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Meko endpoint must be an HTTPS URL without embedded credentials")
        if parsed.query or parsed.fragment:
            raise ValueError("Put credentials in the bearer token, not the endpoint URL")
        if not isinstance(token, str) or not token.strip() or any(c in token for c in "\r\n"):
            raise ValueError("A bearer token is required")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        self._endpoint = endpoint
        self._token = token
        self._timeout = timeout

    @classmethod
    def from_env(cls):
        """Read process environment only; .env files are not loaded implicitly."""
        endpoint = os.environ.get("MEKO_MCP_URL", "")
        token = os.environ.get("MEKO_API_TOKEN", "")
        if not endpoint or not token:
            raise ValueError("Set MEKO_MCP_URL and MEKO_API_TOKEN in the backend environment")
        return cls(endpoint, token)

    async def _invoke(self, name, arguments):
        import httpx
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        async with asyncio.timeout(self._timeout):
            async with httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=self._timeout, follow_redirects=False,
            ) as http_client:
                async with streamable_http_client(
                    self._endpoint, http_client=http_client
                ) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(name, arguments=arguments)
                        return result.model_dump(mode="json", by_alias=True, exclude_none=True)

    def __call__(self, name, arguments):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise MemoryServiceError("Use MekoTransport in a worker thread within async servers")
        try:
            return asyncio.run(self._invoke(name, arguments))
        except Exception:
            # Remote exception messages may include URLs or authentication headers.
            raise MemoryServiceError("Meko connection or tool invocation failed") from None

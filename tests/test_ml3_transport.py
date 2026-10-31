import asyncio
import os
import json
import importlib.util
import unittest
from unittest.mock import patch

from lab_memory import MemoryServiceError
from meko_transport import MekoTransport


class TransportTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("mcp"), "Install requirements.txt for SDK integration test")
    def test_real_sdk_with_in_process_http_server(self):
        """Exercise SDK initialize/tool serialization without opening a socket."""
        import httpx
        seen = []
        real_client = httpx.AsyncClient

        def server(request):
            self.assertEqual(request.headers["authorization"], "Bearer test-token")
            if request.method != "POST":
                return httpx.Response(405)
            payload = json.loads(request.content)
            seen.append(payload)
            if "id" not in payload:
                return httpx.Response(202)
            if payload["method"] == "initialize":
                result = {"protocolVersion": payload["params"]["protocolVersion"],
                          "capabilities": {"tools": {}},
                          "serverInfo": {"name": "offline-test", "version": "1"}}
            elif payload["method"] == "tools/list":
                result = {"tools": [{"name": "context_search", "inputSchema": {"type": "object"}}]}
            elif payload["method"] == "tools/call":
                result = {"content": [{"type": "text", "text": '{"results":{"memory":[]}}'}]}
            else:
                self.fail("Unexpected MCP method")
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": payload["id"], "result": result})

        def client(**kwargs):
            return real_client(transport=httpx.MockTransport(server), **kwargs)

        with patch("httpx.AsyncClient", side_effect=client):
            transport = MekoTransport("https://example.test/mcp", "test-token")
            response = asyncio.run(transport._invoke(
                "context_search", {"datapack_id": "synthetic-scope"}))
        self.assertEqual(json.loads(response["content"][0]["text"])["results"]["memory"], [])
        call = next(item for item in seen if item["method"] == "tools/call")
        self.assertEqual(call["params"]["arguments"]["datapack_id"], "synthetic-scope")
        self.assertEqual(seen[0]["method"], "initialize")

    def test_configuration_rejects_insecure_or_missing_credentials(self):
        for url in ("http://example.test/mcp", "https://secret@example.test/mcp",
                    "https://example.test/mcp?token=secret", "https://example.test/mcp#secret"):
            with self.assertRaises(ValueError):
                MekoTransport(url, "test-token")
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                MekoTransport.from_env()

    def test_transport_does_not_expose_remote_error(self):
        class Broken(MekoTransport):
            async def _invoke(self, name, arguments):
                raise RuntimeError("secret-token")
        with self.assertRaises(MemoryServiceError) as caught:
            Broken("https://example.test/mcp", "test-token")("context_search", {})
        self.assertNotIn("secret-token", str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)

    def test_timeout_becomes_explicit_failure(self):
        class TimedOut(MekoTransport):
            async def _invoke(self, name, arguments):
                async with asyncio.timeout(0.001):
                    await asyncio.sleep(1)
        with self.assertRaises(MemoryServiceError):
            TimedOut("https://example.test/mcp", "test-token")("memory_add", {})

    def test_sync_transport_rejects_running_event_loop(self):
        async def check():
            with self.assertRaises(MemoryServiceError):
                MekoTransport("https://example.test/mcp", "test-token")("context_search", {})
        asyncio.run(check())

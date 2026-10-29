"""Interop tests use the official SDK and a real local HTTP editor fixture."""
import asyncio
import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from studio_next.body_editor_client import LocalEditorClient

HAS_MCP = importlib.util.find_spec("mcp") is not None
if HAS_MCP:
    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.shared.memory import create_client_server_memory_streams
    from studio_next.body_editor_mcp import create_editor_server


SCHEMA = {"type": "object", "properties": {
    "clipId": {"type": "string"},
    "text": {"anyOf": [{"type": "string"}, {"type": "null"}]}},
    "required": ["clipId"], "additionalProperties": False}
TOOLS = [
    {"name": "get_project", "description": "Native project",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "update_text_clip", "description": "Native text", "inputSchema": SCHEMA},
    {"name": "install_workflow_setup", "inputSchema": {"type": "object"}},
]


@unittest.skipUnless(HAS_MCP, "Install the editor extra to test the official MCP protocol")
class EditorMCPTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.requests = []
        self.tools = TOOLS
        self.native_fail = False
        self.delay = 0
        self.active = 0
        self.max_active = 0
        self.hold = None
        self.entered = threading.Event()
        self.state_lock = threading.Lock()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.requests.append(request)
                if request["method"] == "tools/list":
                    result = {"tools": owner.tools}
                else:
                    with owner.state_lock:
                        owner.active += 1
                        owner.max_active = max(owner.max_active, owner.active)
                    try:
                        if owner.hold is not None and request["params"]["arguments"].get("clipId") == "a":
                            owner.entered.set()
                            owner.hold.wait(timeout=3)
                        time.sleep(owner.delay)
                        result = {"content": [{"type": "text", "text": "native"}],
                                  "_meta": {"native": "preserved"}, "isError": owner.native_fail}
                    finally:
                        with owner.state_lock:
                            owner.active -= 1
                body = json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.http.daemon_threads = True
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f"http://127.0.0.1:{self.http.server_port}/mcp"
        self.client = LocalEditorClient(self.endpoint, allowed_tools={
            "get_project": "read", "update_text_clip": "write"})

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()

    async def with_session(self, check, *, access=frozenset({"read", "write"}), export_verifier=None):
        server = create_editor_server(self.client, allowed_access=access,
                                      export_verifier=export_verifier)
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            async with anyio.create_task_group() as group:
                group.start_soon(server.run, *server_streams, server.create_initialization_options())
                async with ClientSession(*client_streams) as session:
                    await session.initialize()
                    await check(session)
                group.cancel_scope.cancel()

    async def test_native_schema_grants_and_write_pass_through_official_protocol(self):
        async def check(session):
            tools = (await session.list_tools()).tools
            self.assertEqual([tool.name for tool in tools], ["get_project", "update_text_clip"])
            self.assertEqual(tools[1].input_schema, SCHEMA)
            result = await session.call_tool("update_text_clip", {"clipId": "native", "text": "Revised"})
            self.assertFalse(result.is_error)
            self.assertEqual(result.content[0].text, "native")
            self.assertEqual(result.meta, {"native": "preserved"})
            self.assertEqual(self.requests[-1]["params"], {
                "name": "update_text_clip", "arguments": {"clipId": "native", "text": "Revised"}})
        await self.with_session(check)

    async def test_read_only_host_cannot_advertise_or_call_writes(self):
        async def check(session):
            self.assertEqual([tool.name for tool in (await session.list_tools()).tools], ["get_project"])
            result = await session.call_tool("update_text_clip", {"clipId": "x"})
            self.assertTrue(result.is_error)
            self.assertFalse(any(row["method"] == "tools/call" for row in self.requests))
        await self.with_session(check, access=frozenset({"read"}))

    async def test_unknown_tools_and_invalid_arguments_never_reach_editor(self):
        async def check(session):
            for name, args in [("install_workflow_setup", {}), ("update_text_clip", {}),
                               ("update_text_clip", {"clipId": 2}),
                               ("update_text_clip", {"clipId": "x", "allowed_access": ["write"]})]:
                result = await session.call_tool(name, args)
                self.assertTrue(result.is_error)
            self.assertFalse(any(row["method"] == "tools/call" for row in self.requests))
            self.assertFalse((await session.call_tool("get_project", {})).is_error)
        await self.with_session(check)

    async def test_native_tool_error_is_preserved_and_session_remains_usable(self):
        async def check(session):
            self.native_fail = True
            result = await session.call_tool("get_project", {})
            self.assertTrue(result.is_error)
            self.assertEqual(result.meta, {"native": "preserved"})
            self.assertEqual(result.content[0].text, "native")
            self.native_fail = False
            self.assertFalse((await session.call_tool("get_project", {})).is_error)
        await self.with_session(check)

    async def test_native_calls_are_serialized(self):
        self.delay = .05
        async def check(session):
            await asyncio.gather(session.call_tool("update_text_clip", {"clipId": "a"}),
                                 session.call_tool("update_text_clip", {"clipId": "b"}))
            self.assertEqual(self.max_active, 1)
        await self.with_session(check)

    async def test_schema_id_and_local_defs_validate_without_schema_network_access(self):
        schema = {"$id": self.endpoint + "/schema", "type": "object",
                  "$defs": {"clip": {"type": "string"}},
                  "properties": {"clipId": {"$ref": "#/$defs/clip"}},
                  "required": ["clipId"]}
        self.tools = [TOOLS[0], {**TOOLS[1], "inputSchema": schema}]
        async def check(session):
            self.assertFalse((await session.call_tool("update_text_clip", {"clipId": "x"})).is_error)
            self.assertTrue((await session.call_tool("update_text_clip", {"clipId": 3})).is_error)
            self.assertEqual(len([row for row in self.requests if row["method"] == "tools/call"]), 1)
        await self.with_session(check)

    async def test_cancelled_queued_write_is_not_later_applied(self):
        self.hold = threading.Event()
        async def check(session):
            scopes, done = {}, {name: anyio.Event() for name in ("a", "b")}
            async def write(name):
                with anyio.CancelScope() as scope:
                    scopes[name] = scope
                    await session.call_tool("update_text_clip", {"clipId": name})
                done[name].set()
            try:
                async with anyio.create_task_group() as group:
                    group.start_soon(write, "a")
                    self.assertTrue(await anyio.to_thread.run_sync(lambda: self.entered.wait(timeout=2)))
                    group.start_soon(write, "b")
                    while "b" not in scopes:
                        await anyio.sleep(.001)
                    await anyio.sleep(.03)
                    scopes["b"].cancel()
                    await done["b"].wait()
                    await anyio.sleep(.03)
                    self.hold.set()
                    await done["a"].wait()
                    await anyio.sleep(.03)
                calls = [row for row in self.requests if row["method"] == "tools/call"]
                self.assertEqual([row["params"]["arguments"]["clipId"] for row in calls], ["a"])
            finally:
                self.hold.set()
        await self.with_session(check)

    async def test_cancelled_inflight_write_keeps_lock_until_native_response(self):
        self.hold = threading.Event()
        async def check(session):
            scopes, done = {}, {name: anyio.Event() for name in ("a", "b")}
            async def write(name):
                with anyio.CancelScope() as scope:
                    scopes[name] = scope
                    await session.call_tool("update_text_clip", {"clipId": name})
                done[name].set()
            try:
                async with anyio.create_task_group() as group:
                    group.start_soon(write, "a")
                    self.assertTrue(await anyio.to_thread.run_sync(lambda: self.entered.wait(timeout=2)))
                    scopes["a"].cancel()
                    await done["a"].wait()
                    group.start_soon(write, "b")
                    await anyio.sleep(.05)
                    calls = [row for row in self.requests if row["method"] == "tools/call"]
                    self.assertEqual(len(calls), 1)
                    self.hold.set()
                    await done["b"].wait()
                self.assertEqual(self.max_active, 1)
            finally:
                self.hold.set()
        await self.with_session(check)

    async def test_export_verifier_is_read_only_opt_in_and_no_native_rpc(self):
        observed = []
        def verifier(path, expected=None):
            observed.append((path, expected))
            if path != "/trusted/export.mp4":
                raise ValueError("outside selected export")
            return {"physical_export_verified": True, "artistic_quality_approved": False}

        async def check(session):
            catalog = {tool.name: tool for tool in (await session.list_tools()).tools}
            self.assertIn("zx7_verify_native_export", catalog)
            good = await session.call_tool("zx7_verify_native_export", {
                "path": "/trusted/export.mp4", "expected": {"require_audio": True}})
            self.assertFalse(good.is_error)
            self.assertEqual(json.loads(good.content[0].text)["physical_export_verified"], True)
            self.assertEqual(observed, [("/trusted/export.mp4", {"require_audio": True})])
            for arguments in ({}, {"path": 12}, {"path": "/trusted/export.mp4", "expected": {"unknown": 1}},
                              {"path": "/etc/passwd"}):
                denied = await session.call_tool("zx7_verify_native_export", arguments)
                self.assertTrue(denied.is_error)
            self.assertFalse(any(x["method"] == "tools/call" for x in self.requests))
        await self.with_session(check, export_verifier=verifier)

        async def no_read(session):
            self.assertNotIn("zx7_verify_native_export", [
                tool.name for tool in (await session.list_tools()).tools])
            self.assertTrue((await session.call_tool("zx7_verify_native_export", {
                "path": "/trusted/export.mp4"})).is_error)
        await self.with_session(no_read, access=frozenset({"write"}), export_verifier=verifier)
        self.assertEqual(len(observed), 1)

    def test_missing_host_grant_or_remote_schema_reference_fails_closed(self):
        self.tools = [TOOLS[0]]
        with self.assertRaisesRegex(ValueError, "absent"):
            create_editor_server(self.client)
        self.tools = [TOOLS[0], {**TOOLS[1], "inputSchema": {"type": "object",
            "properties": {"x": {"$ref": "https://example.invalid/schema"}}}}]
        with self.assertRaisesRegex(ValueError, "reference"):
            create_editor_server(self.client, allowed_access=frozenset({"read", "write"}))

    async def test_real_stdio_client_initialize_list_and_call(self):
        with tempfile.TemporaryDirectory() as root:
            roots = {name: str(Path(root) / name) for name in ("projects", "staging", "outputs")}
            config = {"endpoint": self.endpoint, "projects_root": roots["projects"],
                      "staging_root": roots["staging"], "outputs_root": roots["outputs"],
                      "allowed_tools": {"get_project": "read", "update_text_clip": "write"},
                      "allowed_access": ["read", "write"]}
            path = Path(root) / "host.json"
            path.write_text(json.dumps(config))
            params = StdioServerParameters(command=sys.executable, args=["-m", "studio_next.body_editor_mcp",
                                            "--config", str(path)])
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    initialized = await session.initialize()
                    self.assertEqual(initialized.server_info.name, "zx7-native-editor")
                    self.assertEqual((await session.list_tools()).tools[1].input_schema, SCHEMA)
                    self.assertFalse((await session.call_tool("get_project", {})).is_error)
                    self.assertFalse((await session.call_tool("update_text_clip", {"clipId": "x", "text": "stdio"})).is_error)
                    self.assertTrue((await session.call_tool("install_workflow_setup", {})).is_error)
            inspected = subprocess.run([sys.executable, "-m", "studio_next.body_editor_mcp", "--config", str(path),
                                        "--print-launch-config"], capture_output=True, text=True, timeout=10)
            self.assertEqual(inspected.returncode, 0, inspected.stderr)
            self.assertEqual(json.loads(inspected.stdout), {"endpoint": self.endpoint,
                "projects_root": roots["projects"], "staging_root": roots["staging"], "outputs_root": roots["outputs"]})


if __name__ == "__main__":
    unittest.main()

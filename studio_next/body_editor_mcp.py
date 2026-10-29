"""Standard MCP stdio bridge to a host-granted local native editor.

The optional official SDK owns protocol negotiation and stdio framing. Native
schemas and results remain native; this module adds host grants, input-schema
validation and serial execution for the editor's single active project.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
from pathlib import Path
import sys

from .body_editor_client import (
    EditorAccessError, EditorClientError, EditorToolError, _access_modes,
)


def _local_schema_references(schema):
    """Validation must never fetch a schema or another hosted dependency."""
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key in ("$ref", "$dynamicRef", "$recursiveRef") and (
                    not isinstance(value, str) or not value.startswith("#")):
                raise ValueError("Native schema has a nonlocal reference")
            _local_schema_references(value)
    elif isinstance(schema, list):
        for item in schema:
            _local_schema_references(item)


def create_editor_server(client, *, allowed_access=frozenset({"read"}),
                         export_verifier=None):
    """Return the official SDK server; discovery never expands host grants.

    Dependencies are imported here so the stdlib BODY remains usable without
    the optional ``editor`` extra. Schemas are checked once against actual
    discovery before the protocol server can advertise any operation.
    """
    import anyio
    import jsonschema
    from mcp.server import Server
    from mcp import types

    access = _access_modes(allowed_access)
    native = {tool["name"]: tool for tool in client.list_tools()}
    grants = dict(client.allowed_tools)
    if set(grants) - set(native):
        raise ValueError("Host-granted native editor tool is absent from discovery")
    tools = {}
    validators = {}
    for name, mode in grants.items():
        if mode not in access:
            continue
        schema = native[name]["inputSchema"]
        _local_schema_references(schema)
        validator = jsonschema.validators.validator_for(schema)
        validator.check_schema(schema)
        validators[name] = validator(schema)
        tools[name] = types.Tool.model_validate(native[name])
    verified_export_name = "zx7_verify_native_export"
    if export_verifier is not None:
        if not callable(export_verifier) or verified_export_name in native:
            raise ValueError("Invalid host export verifier or native tool name collision")
        if "read" in access:
            schema = {"type": "object",
                      "properties": {
                          "path": {"type": "string"},
                          "expected": {"type": "object",
                                       "properties": {
                                           "width": {"type": "integer", "minimum": 1},
                                           "height": {"type": "integer", "minimum": 1},
                                           "duration_seconds": {"type": "number", "exclusiveMinimum": 0},
                                           "require_audio": {"type": "boolean"}},
                                       "additionalProperties": False}},
                      "required": ["path"], "additionalProperties": False}
            tools[verified_export_name] = types.Tool(
                name=verified_export_name,
                description="Decode and independently verify an authorized finished native video export; not an artistic-quality score",
                inputSchema=schema)
            validators[verified_export_name] = jsonschema.Draft202012Validator(schema)
    lock = anyio.Lock()

    def failed(message):
        return types.CallToolResult(is_error=True,
            content=[types.TextContent(type="text", text=message)])

    async def list_tools(_ctx, _params):
        return types.ListToolsResult(tools=list(tools.values()))

    async def call_tool(_ctx, params):
        name = params.name
        if name not in tools:
            return failed("Native tool is not granted for this MCP session")
        arguments = params.arguments if params.arguments is not None else {}
        try:
            validators[name].validate(arguments)
        except jsonschema.ValidationError as exc:
            return failed("Invalid native tool arguments: " + exc.message)
        if name == verified_export_name:
            try:
                async with lock:
                    with anyio.CancelScope(shield=True):
                        proof = await anyio.to_thread.run_sync(
                            lambda: export_verifier(arguments["path"], expected=arguments.get("expected")),
                            abandon_on_cancel=False)
                return types.CallToolResult(is_error=False, content=[
                    types.TextContent(type="text", text=json.dumps(proof, allow_nan=False))])
            except (ValueError, OSError, subprocess.SubprocessError) as exc:
                return failed("Independent native export verification failed: " + str(exc))
        try:
            # Do not abandon a possibly applied write on protocol cancellation.
            # The lock stays held until the bounded native HTTP call finishes.
            async with lock:
                with anyio.CancelScope(shield=True):
                    result = await anyio.to_thread.run_sync(
                        lambda: client.call(name, arguments, allowed_access=access),
                        abandon_on_cancel=False)
            return types.CallToolResult.model_validate(result)
        except EditorToolError as exc:
            return types.CallToolResult.model_validate(exc.result)
        except (EditorAccessError, PermissionError, ValueError) as exc:
            return failed(str(exc))
        except EditorClientError as exc:
            uncertain = (" A write may already have occurred; inspect native state before retrying."
                         if grants[name] == "write" else "")
            return failed(str(exc) + uncertain)

    return Server("zx7-native-editor", version="0.1.0",
                  on_list_tools=list_tools, on_call_tool=call_tool)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path,
                        help="Host-owned editor grants and workspace roots")
    parser.add_argument("--print-launch-config", action="store_true",
                        help="Validate and print canonical roots without contacting the editor")
    options = parser.parse_args(argv)
    try:
        from .body_editor_policy import load_editor_config
        config = load_editor_config(options.config)
        if options.print_launch_config:
            print(json.dumps({"endpoint": config.endpoint,
                              "projects_root": str(config.projects_root),
                              "staging_root": str(config.staging_root),
                              "outputs_root": str(config.outputs_root)}, allow_nan=False))
            return 0
        export_verifier = None
        if config.verify_native_exports:
            from .body_editor_export import verify_native_editor_export
            export_verifier = lambda path, expected=None: verify_native_editor_export(
                path, policy=config._policy, expected=expected)
        server = create_editor_server(config.client(), allowed_access=config.allowed_access,
                                      export_verifier=export_verifier)

        async def serve():
            from mcp.server.stdio import stdio_server
            async with stdio_server() as (read, write):
                await server.run(read, write, server.create_initialization_options())

        asyncio.run(serve())
        return 0
    except (ValueError, OSError, EditorClientError, ImportError) as exc:
        print(f"Native editor MCP startup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

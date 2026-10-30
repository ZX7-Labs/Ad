"""Use existing installed ZX7 creative operations through the same brain/body ABI.

No MD files, tool scripts from the model, grant escalation or new render
implementations. The legacy trusted ToolCatalog remains the execution owner.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from .body_integration import body_catalog


class InstalledBodyAdapter:
    """Live connected source for CapabilityGateway, backed by actual BODY code."""

    def __init__(self, workspace, *, allowed_access=("read", "write"),
                 editor_client=None):
        allowed = frozenset(allowed_access)
        if not allowed or not allowed.issubset({"read", "write"}):
            raise ValueError("BODY bridge can only receive explicit local read/write grants")
        self._workspace = Path(workspace).resolve()
        self._editor_client = editor_client
        self._allowed_access = allowed
        self._grants = None

    def _installed(self):
        catalog = body_catalog(self._workspace, editor_client=self._editor_client)
        enabled = catalog.executable_ids(self._allowed_access)
        descriptors = {item["id"]: item for item in catalog.discover()
                       if item["id"] in enabled}
        return catalog, descriptors

    async def list_tools(self):
        _, permitted = self._installed()
        # These data come only from the actual installed local ToolCatalog,
        # never AI text, old app documentation or guessed future APIs.
        return SimpleNamespace(tools=[
            SimpleNamespace(name=ident,
                            description=detail["capability"] + ". " +
                                        detail["description"],
                            input_schema=detail["schema"])
            for ident, detail in sorted(permitted.items())],
            nextCursor=None)

    def trusted_grants(self):
        _, permitted = self._installed()
        return {name: spec["access"] for name, spec in permitted.items()}

    async def call_tool(self, name, inputs):
        catalog, permitted = self._installed()
        if name not in permitted:
            raise PermissionError("BODY operation no longer installed or granted")
        if permitted[name]["access"] not in self._allowed_access:
            raise PermissionError("BODY operation forbidden by host")
        # This is the SAME original trusted runner (including media rights,
        # output custody, durable publication and input validation).
        result = await asyncio.to_thread(
            catalog.invoke, name, inputs, allowed_access=self._allowed_access)
        return SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="text", text=json.dumps(
                result, ensure_ascii=False, allow_nan=False))])


async def connect_installed_zx7_body(workspace, *, allowed_access=("read", "write"),
                                    editor_client=None):
    """Create the universal execution gateway from a real installed BODY."""
    from .capability_gateway import CapabilityGateway

    adapter = InstalledBodyAdapter(workspace, allowed_access=allowed_access,
                                   editor_client=editor_client)
    gateway = CapabilityGateway({"zx7": (adapter, adapter.trusted_grants())})
    await gateway.refresh()
    return gateway

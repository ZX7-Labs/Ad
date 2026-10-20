"""Discoverable, least-privilege tool catalog. No arbitrary shell commands."""
from dataclasses import dataclass
from typing import Callable
from .contracts import ToolSpec, _json_like

@dataclass
class _Entry:
    spec: ToolSpec
    runner: Callable | None

class ToolCatalog:
    def __init__(self):
        self._tools: dict[str,_Entry]={}
    def register(self,spec:ToolSpec,runner:Callable|None=None):
        if spec.tool_id in self._tools:
            raise ValueError(f"Duplicate tool {spec.tool_id}")
        if runner is not None and not callable(runner):
            raise TypeError("Runner must be a trusted registered callable")
        self._tools[spec.tool_id]=_Entry(spec,runner)
    def discover(self):
        return [entry.spec.public() for entry in self._tools.values()]
    def executable_ids(self, allowed_access=None):
        """Registered is not sufficient: proposals must respect granted permissions."""
        permitted=None if allowed_access is None else frozenset(allowed_access)
        return {k for k,v in self._tools.items()
                if v.spec.status=="installed" and v.runner is not None
                and (permitted is None or v.spec.access in permitted)}
    def invoke(self,tool_id,inputs,allowed_access=frozenset({"read"})):
        entry=self._tools.get(tool_id)
        if entry is None:raise ValueError(f"Unknown tool {tool_id!r}")
        spec=entry.spec
        if spec.status!="installed" or entry.runner is None:
            raise RuntimeError(f"Tool {tool_id} unavailable: {spec.status}")
        if spec.access not in allowed_access:
            raise PermissionError(f"Tool {tool_id} requires {spec.access} access")
        if not isinstance(inputs,dict):raise TypeError("Tool inputs must be an object")
        # The LLM only provides data: code entry points must be installed by a
        # trusted project maintainer. Do not eval/exec/subprocess LLM strings.
        arguments=_json_like(inputs)
        required=spec.operation_schema.get("required",[])
        for item in required:
            if item not in arguments:raise ValueError(f"Missing {tool_id} input: {item}")
        result=entry.runner(arguments)
        return _json_like(result)

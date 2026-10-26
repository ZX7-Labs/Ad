"""Permissioned executor for prevalidated film tool graphs.

This is not a renderer or a film-quality gate. It never treats finishing
registered tool calls as proof that a useful video has been produced.
"""
from dataclasses import dataclass, field
import hashlib
import json

from .contracts import _json_like
from .film_ir import validate_film_ir
from .registry import ToolCatalog


@dataclass
class GraphOutcome:
    status: str
    completed_steps: list[str] = field(default_factory=list)
    output_digests: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    claim: str = "Tool execution is not verified video, sound or artistic approval."

    def public(self):
        return {
            "status": self.status,
            "completed_steps": self.completed_steps,
            "output_digests": self.output_digests,
            "errors": self.errors,
            "trace": self.trace,
            "claim": self.claim,
        }


def _walk(value, allowed_dependencies: set[str], *, resolve=None):
    """Validate node-result references before writes, then resolve during execution.

    A reference is the complete JSON object {"$node_output": "node_id"}.
    This deliberately excludes paths, code and model-supplied shell commands.
    """
    if isinstance(value, dict):
        if "$node_output" in value:
            if len(value) != 1 or not isinstance(value["$node_output"], str):
                raise ValueError("Invalid node-result reference object")
            ref = value["$node_output"]
            if ref not in allowed_dependencies:
                raise ValueError("Node-result reference needs declared dependency: " + ref)
            if resolve is None:
                return None
            if ref not in resolve:
                raise ValueError("Missing completed output of dependency: " + ref)
            return _json_like(resolve[ref])
        return {key: _walk(item, allowed_dependencies, resolve=resolve)
                for key, item in value.items()}
    if isinstance(value, list):
        return [_walk(item, allowed_dependencies, resolve=resolve) for item in value]
    return value


def execute_graph(ir: dict, catalog: ToolCatalog, *, fact_ids: set[str],
                  allowed_access=frozenset({"read"}), max_steps=100):
    """Execute only an already-audited graph via trusted installed adapters.

    max_steps limits compute/side-effect risk, never creative scene count.
    All references are checked before any tool is invoked. No rollback or
    automatic retry is claimed after a tool has actually produced side effects.
    """
    if not isinstance(catalog, ToolCatalog):
        raise TypeError("Trusted ToolCatalog required")
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 1:
        raise ValueError("Finite execution step budget required")
    allowed_access = frozenset(allowed_access)
    if not allowed_access.issubset({"read", "write", "network", "paid"}):
        raise ValueError("Invalid access grant")
    try:
        validation = validate_film_ir(
            ir, installed_tool_ids=catalog.executable_ids(allowed_access),
            fact_ids=fact_ids)
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        return GraphOutcome("blocked", errors=["Malformed film graph: " + str(exc)])
    if not validation.render_ready:
        return GraphOutcome("blocked", errors=validation.errors + validation.warnings)
    nodes = ir["tool_graph"]
    if len(nodes) > max_steps:
        return GraphOutcome("blocked", errors=["Execution step budget exceeded"])
    lookup = {node["id"]: node for node in nodes}
    # Preflight all input references, including later nodes, before side effects.
    try:
        for node in nodes:
            inputs = _json_like(node["inputs"])
            _walk(inputs, set(node.get("depends_on", [])))
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        return GraphOutcome("blocked", errors=["Unresolvable graph inputs: " + str(exc)])

    outputs = {}
    completed = []
    digests = {}
    trace = []
    for node_id in validation.order:
        node = lookup[node_id]
        try:
            resolved = _walk(node["inputs"], set(node.get("depends_on", [])),
                             resolve=outputs)
            result = catalog.invoke(node["tool_id"], resolved,
                                    allowed_access=allowed_access)
            canonical = json.dumps(result, sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=False, allow_nan=False).encode("utf-8")
            digest = hashlib.sha256(canonical).hexdigest()
        except Exception as exc:
            # Preserve completed-step trace without leaking sensitive inputs.
            return GraphOutcome("failed_partial" if completed else "failed",
                                completed, digests,
                                [f"Step {node_id} failed: {type(exc).__name__}: {exc}"],
                                trace)
        outputs[node_id] = result
        completed.append(node_id)
        digests[node_id] = digest
        trace.append({"node_id": node_id, "tool_id": node["tool_id"],
                      "result_sha256": digest})
    return GraphOutcome("graph_steps_completed", completed, digests, [], trace)

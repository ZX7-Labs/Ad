"""Model-neutral, source-agnostic runtime for actual host-granted BODY operations.

Never infer execution rights from a model, retrieved tool annotation, readme,
or a tool name. Local engine and official MCP adapters expose list_tools /
call_tool. The host registers grants and optional fact readers. A compact
brain needs only capability IDs returned by search + an exact input contract.
No hardcoded video, VFX, animation, or design tool names.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import json
from collections.abc import Mapping

from .capability_fabric import CapabilityContractError, CapabilityFabric
from .body_editor_mcp import _local_schema_references


class CapabilityExecutionError(ValueError):
    """Rejected BEFORE any native dispatch; no guessed operation is allowed."""


def _wire(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


class CapabilityGateway:
    """Trusted host-owned source connections, not a model/plugin write proxy.

    bindings: namespace -> (connected_session, trusted grants, [prerequisites],
                             [trusted async or sync fact reader]).
    The fact reader accepts no model-provided data and returns a mapping of
    host-attested boolean facts. Missing facts deny prerequisite admission.
    """

    def __init__(self, bindings: Mapping):
        if not isinstance(bindings, Mapping) or not 1 <= len(bindings) <= 256:
            raise CapabilityExecutionError("Connected host-bound source inventory is required")
        self._bindings = {}
        self._locks = {}
        for namespace, entry in bindings.items():
            if not isinstance(entry, tuple) or len(entry) not in (2, 3, 4):
                raise CapabilityExecutionError("Source requires a real connection and grants")
            session, grants = entry[:2]
            requires = entry[2] if len(entry) >= 3 else {}
            facts = entry[3] if len(entry) == 4 else None
            if (not callable(getattr(session, "list_tools", None)) or
                    not callable(getattr(session, "call_tool", None)) or
                    not isinstance(grants, Mapping) or
                    any(not isinstance(k, str) or v not in ("read", "write")
                        for k, v in grants.items()) or
                    (facts is not None and not callable(facts))):
                raise CapabilityExecutionError("Host source bindings are invalid")
            self._bindings[namespace] = (session, dict(grants), copy.deepcopy(requires), facts)
            self._locks[namespace] = asyncio.Lock()
        self._fabric = None
        self._events = []

    async def refresh(self):
        """Rebuild from real connected sources, e.g. after MCP list_changed.

        Refreshing changes the contract digest. Previously selected handles
        never gain authority under an updated ABI or grant set.
        """
        discovery = {name: (entry[0], entry[1], entry[2])
                     for name, entry in self._bindings.items()}
        fabric = await CapabilityFabric.from_connections(discovery)
        self._fabric = fabric
        return fabric.overview()

    def _current(self):
        if self._fabric is None:
            raise CapabilityExecutionError("Discover the real connected BODY before use")
        return self._fabric

    def search(self, query, *, limit=6):
        return self._current().search(query, limit=limit)

    def describe(self, operation_id, *, revision):
        return self._current().describe(operation_id, revision=revision)

    def evidence(self):
        """Only bounded identity/digest and outcome, never raw private media."""
        return copy.deepcopy(self._events)

    async def invoke(self, operation_id, *, revision, inputs):
        """One model-selected operation; never auto-retry uncertain writes.

        Always re-discover live tool ABI and grants under a per-source lock
        before the call. State gates are advisory in the catalog but enforced
        here when a trusted source explicitly declares prerequisites.
        Individual native engines still enforce their own path/rights policies.
        """
        prior = self._current()
        record = prior.resolve(operation_id, revision=revision)
        namespace, name = record["source"], record["native_name"]
        async with self._locks[namespace]:
            # Revalidate ONLY the selected engine, not every connected
            # creative app on each frame/operation. Cross-domain scaling
            # must not make single-engine edits O(all connected tools).
            session, grants, conditions, fact_reader = self._bindings[namespace]
            response = await session.list_tools()
            cursor = getattr(response, "nextCursor",
                             getattr(response, "next_cursor", None))
            if isinstance(response, dict):
                cursor = response.get("nextCursor", response.get("next_cursor"))
            if cursor not in (None, ""):
                raise CapabilityExecutionError("Incomplete current host tool inventory")
            advertised = (response.get("tools") if isinstance(response, dict)
                          else getattr(response, "tools", None))
            fresh = CapabilityFabric({namespace: (advertised, grants, conditions)})
            live_record = fresh.resolve(operation_id, revision=fresh.revision)
            for field in ("access", "input_schema", "description", "requires"):
                if record[field] != live_record[field]:
                    raise CapabilityExecutionError(
                        "Native operation contract changed; rediscover capability")
            if name not in grants or grants[name] != record["access"]:
                raise CapabilityExecutionError("Native grant changed before operation")
            current = prior
            schema = copy.deepcopy(record["input_schema"])
            _local_schema_references(schema)
            import jsonschema
            if not isinstance(inputs, dict):
                raise CapabilityExecutionError("BODY inputs must be a structured object")
            # Host-named top-level fields are an ABI. Unspecified top-level
            # fields invite model hallucinations; intentionally open nested
            # artistic parameters remain unrestricted by this preflight.
            if (isinstance(schema.get("properties"), dict) and
                    "additionalProperties" not in schema and
                    "patternProperties" not in schema):
                schema["additionalProperties"] = False
            validator_type = jsonschema.validators.validator_for(schema)
            validator_type.check_schema(schema)
            invalid = next(validator_type(schema).iter_errors(inputs), None)
            if invalid is not None:
                raise CapabilityExecutionError(
                    "Invalid native parameters (" + str(invalid.validator)[:40] + ")")
            requirements = record["requires"]
            if requirements:
                if fact_reader is None:
                    raise CapabilityExecutionError(
                        "Required machine state cannot be independently established")
                facts = fact_reader()
                if inspect.isawaitable(facts):
                    facts = await facts
                readiness = current.check_prerequisites(
                    operation_id, revision=revision, trusted_facts=facts)
                if not readiness["admissible"]:
                    raise CapabilityExecutionError(
                        "Machine prerequisite absent or unknown; inspect host state")
            digest = hashlib.sha256(_wire(inputs).encode("utf-8")).hexdigest()
            trace = {"operation_id": operation_id, "catalog_revision": revision,
                     "input_sha256": digest, "access": record["access"],
                     "state": "submitted_unconfirmed"}
            self._events.append(trace)
            try:
                # One submission only; uncertain writes require reconciliation.
                result = await session.call_tool(name, copy.deepcopy(inputs))
            except BaseException:
                trace["state"] = ("read_failed" if record["access"] == "read"
                                  else "write_uncertain_reconciliation_required")
                raise
            failure = result.get("is_error", result.get("isError", False)) if isinstance(
                result, dict) else getattr(result, "is_error",
                                           getattr(result, "isError", False))
            if failure:
                trace["state"] = ("read_failed" if record["access"] == "read"
                                  else "write_uncertain_reconciliation_required")
                return {"state": trace["state"], "operation_id": operation_id,
                        "native_result": result}
            trace["state"] = "host_reported_success_unverified"
            return {"state": trace["state"], "operation_id": operation_id,
                    "native_result": result}

"""ZX7 BODY machine-readable capability fabric, independent of creative domain.

The host owns authorization and actual tool schemas. A replaceable brain sees a
tiny discovery interface, searches relevant *installed/granted* operations and
asks for one exact schema. This is not a model prompt, a creative template or a
second permission layer. New source adapters contribute the same native shape.
No README/Markdown parsing, hosted search, embeddings or vendor dependency.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Mapping


class CapabilityContractError(ValueError):
    """An untrusted, absent, stale or invalid capability was selected."""


def _field(item, key, default=None):
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


def _wire(item):
    return json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def _tokens(value):
    # CamelCase and dot, slash, dash, underscore boundaries. This is small,
    # deterministic local retrieval, not a claim of semantic intelligence.
    value = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    return set(re.findall(r"[^\W_]+", value.casefold(), re.UNICODE))


class CapabilityFabric:
    """Immutable, exact host-granted capability snapshot.

    Sources: mapping of stable namespace -> (MCP tool descriptions, trusted
    host grant map of tool name to 'read' or 'write'). A connected engine
    contributes only actual tools it advertised and the host explicitly
    authorized. Snapshots can be replaced when a source's catalog changes;
    stale references are rejected by the next snapshot's revision.
    """

    def __init__(self, sources: Mapping):
        if not isinstance(sources, Mapping) or not sources or len(sources) > 256:
            raise CapabilityContractError("At least one bounded real source is required")
        records = {}
        for namespace, pair in sources.items():
            if (not isinstance(namespace, str) or
                    re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", namespace) is None or
                    not isinstance(pair, tuple) or len(pair) != 2):
                raise CapabilityContractError("Source identity and trusted grants required")
            tools, grants = pair
            if (not isinstance(tools, (list, tuple)) or len(tools) > 5000 or
                    not isinstance(grants, Mapping) or
                    any(not isinstance(k, str) or v not in ("read", "write")
                        for k, v in grants.items())):
                raise CapabilityContractError("Native source catalog/grants malformed")
            seen = set()
            for tool in tools:
                name = _field(tool, "name")
                schema = _field(tool, "input_schema", _field(tool, "inputSchema"))
                if (not isinstance(name, str) or not 0 < len(name) <= 160 or
                        any(ord(ch) < 32 for ch in name) or name in seen or
                        not isinstance(schema, dict)):
                    raise CapabilityContractError("Duplicate or malformed native tool")
                seen.add(name)
                if name not in grants:
                    continue
                identity = namespace + "/" + name
                desc = _field(tool, "description", "")
                if not isinstance(desc, str):
                    desc = ""
                # Avoid copying untrusted descriptions and giant schemas into
                # model context. Full trusted source schema remains local.
                summary = " ".join(desc[:1024].split())[:128]
                try:
                    schema_bytes = len(_wire(schema).encode("utf-8"))
                except (TypeError, ValueError, RecursionError) as exc:
                    raise CapabilityContractError("Unserializable native schema") from exc
                if schema_bytes > 512_000:
                    raise CapabilityContractError("Native schema exceeds host admission budget")
                records[identity] = {
                    "operation_id": identity, "source": namespace,
                    "native_name": name, "description": summary,
                    "access": grants[name],
                    "input_schema": json.loads(_wire(schema)),
                    "schema_bytes": schema_bytes,
                    "name_tokens": _tokens(name + " " + namespace),
                    "description_tokens": _tokens(summary),
                }
        if not records:
            raise CapabilityContractError("No executable host-granted capabilities")
        self._records = records
        self._namespaces = sorted(sources)
        # A deterministic contract revision invalidates a stale model-side
        # selection even when the *name* is reused for a different ABI/grant.
        self.revision = hashlib.sha256(_wire([{
            "id": key, "access": value["access"],
            "summary": value["description"], "schema": value["input_schema"]
        } for key, value in sorted(records.items())]).encode("utf-8")).hexdigest()

    @property
    def count(self):
        return len(self._records)

    def overview(self):
        counts = {key: 0 for key in self._namespaces}
        for value in self._records.values():
            counts[value["source"]] += 1
        return {"revision": self.revision, "operation_count": self.count,
                "sources": counts, "discovery": "search_then_describe"}

    def search(self, query: str, *, limit: int = 6):
        if (not isinstance(query, str) or not query.strip() or
                len(query.encode("utf-8")) > 160 or
                type(limit) is not int or not 1 <= limit <= 8):
            raise CapabilityContractError("Use a bounded descriptive capability query")
        terms = _tokens(query)
        if not terms:
            raise CapabilityContractError("Search query has no searchable terms")
        scored = []
        for ident, record in self._records.items():
            name_hits = terms & record["name_tokens"]
            desc_hits = terms & record["description_tokens"]
            if not (name_hits or desc_hits):
                continue
            # Deterministic all-term preference, then stronger identity match.
            covered = len(name_hits | desc_hits)
            score = (100 * (covered == len(terms)) + 10 * covered +
                     5 * len(name_hits) + len(desc_hits))
            scored.append((-score, ident, record))
        scored.sort(key=lambda x: (x[0], x[1]))
        items = []
        for _, ident, record in scored[:limit]:
            schema = record["input_schema"]
            props = schema.get("properties")
            param_names = list(props)[:6] if isinstance(props, dict) else []
            items.append({"id": ident, "description": record["description"][:96],
                          "access": record["access"],
                          "parameters_sample": param_names})
        return {"revision": self.revision, "matches": items,
                "has_more": len(scored) > limit}

    def describe(self, operation_id: str, *, revision: str, max_schema_bytes=16_384):
        record = self.resolve(operation_id, revision=revision)
        if type(max_schema_bytes) is not int or not 512 <= max_schema_bytes <= 65_536:
            raise CapabilityContractError("Invalid bounded schema budget")
        if record["schema_bytes"] > max_schema_bytes:
            return {"operation_id": operation_id, "revision": self.revision,
                    "schema_too_large": True,
                    "required_schema_bytes": record["schema_bytes"]}
        return {"operation_id": operation_id, "revision": self.revision,
                "access": record["access"],
                "input_schema": record["input_schema"],
                "description": record["description"]}

    def resolve(self, operation_id: str, *, revision: str):
        if not isinstance(revision, str) or revision != self.revision:
            raise CapabilityContractError("Stale capability catalog revision")
        if not isinstance(operation_id, str) or operation_id not in self._records:
            raise CapabilityContractError("Unknown or ungranted BODY capability")
        return copy.deepcopy(self._records[operation_id])

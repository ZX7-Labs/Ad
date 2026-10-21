"""Live, bounded, model-neutral control surface for the installed ZX7 BODY.

This is a host-side API, not a creative prompt or a new renderer.  A future
brain discovers operations as needed, authors its own Film IR, and observes
real persisted tool states.  The model cannot grant itself execution rights.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .film_ir import validate_film_ir


class BodyCommandRejected(ValueError):
    """A rejected command has not started a renderer."""


@dataclass(frozen=True)
class BodyAuthority:
    """Created by the trusted owner/host, never deserialized from AI output."""
    operations: frozenset[str] = field(default_factory=frozenset)
    fact_ids: frozenset[str] = field(default_factory=frozenset)
    tool_access: frozenset[str] = field(default_factory=lambda: frozenset({"read"}))

    def __post_init__(self):
        allowed = {"submit", "pause", "cancel", "resume", "retry"}
        access = {"read", "write", "network", "paid"}
        if (not isinstance(self.operations, frozenset)
                or not self.operations <= allowed
                or not isinstance(self.fact_ids, frozenset)
                or not all(isinstance(v, str) and v for v in self.fact_ids)
                or not isinstance(self.tool_access, frozenset)
                or not self.tool_access <= access):
            raise ValueError("Invalid host-owned body authority")


class LiveBodySignal:
    """Connects existing tool catalog, persistent worker and observed artifacts.

    The model has only the discover/describe/observe/command methods below.
    It cannot mutate the catalog, choose its own permission set, install a
    plugin, execute shell text, or accept imagined tool output as evidence.
    """

    VERSION = "zx7-body-signal/1"

    def __init__(self, coordinator, *, authority: BodyAuthority,
                 catalog_factory: Callable | None = None):
        if not isinstance(authority, BodyAuthority):
            raise TypeError("Use an out-of-band BodyAuthority from the host")
        self._coordinator = coordinator
        self._authority = authority
        if catalog_factory is None:
            from .body_integration import body_catalog
            catalog_factory = body_catalog
        self._catalog_factory = catalog_factory

    def _catalog(self):
        return self._catalog_factory(self._coordinator.projects)

    @staticmethod
    def _bounded_text(value, *, max_length=256):
        if not isinstance(value, str):
            return ""
        return value[:max_length]

    def discover(self, *, query=None, cursor=0, limit=20):
        """Paged live affordances, not a megabyte handbook in model context.

        Includes unavailable capabilities as clearly blocked candidates.  A
        selected operation's full schema is fetched separately by describe().
        """
        if (query is not None and
                (not isinstance(query, str) or len(query) > 1000)):
            raise BodyCommandRejected("Capability query must be short text")
        if (type(cursor) is not int or cursor < 0 or type(limit) is not int
                or not 1 <= limit <= 100):
            raise BodyCommandRejected("Invalid capability pagination")
        specs = self._catalog().discover()
        selected = []
        for item in specs:
            if not isinstance(item, dict):
                raise RuntimeError("Untrusted installed catalog structure")
            title = " ".join(str(item.get(k, "")) for k in
                             ("id", "capability", "description"))
            if query and query.casefold() not in title.casefold():
                continue
            access = item.get("access")
            installed = item.get("status") == "installed"
            permitted = access in self._authority.tool_access
            selected.append({
                "id": item.get("id"), "capability": item.get("capability"),
                "status": ("available" if installed and permitted else
                           "permission_required" if installed else "needs_setup"),
                "access": access,
            })
        selected.sort(key=lambda x: str(x["id"]))
        page = selected[cursor:cursor + limit]
        next_cursor = cursor + limit if cursor + limit < len(selected) else None
        return {"protocol": self.VERSION, "abilities": page,
                "next_cursor": next_cursor, "matching": len(selected),
                "live_registry": True}

    def describe(self, tool_id):
        if not isinstance(tool_id, str) or not tool_id:
            raise BodyCommandRejected("Exact registered tool identity required")
        specs = self._catalog().discover()
        for item in specs:
            if item.get("id") != tool_id:
                continue
            permitted = item.get("access") in self._authority.tool_access
            installed = item.get("status") == "installed"
            if not installed or not permitted:
                return {"protocol": self.VERSION, "id": tool_id,
                        "status": "permission_required" if installed else "needs_setup"}
            # A compact executable technical ABI: no art/template/shot decisions.
            return {"protocol": self.VERSION, "id": tool_id,
                    "status": "available", "access": item["access"],
                    "input_schema": item.get("schema", {}),
                    "limitations": item.get("limitations", [])}
        raise BodyCommandRejected("Unregistered tool identity")

    def observe(self, job_id, *, include_artifacts=False):
        """Read *measured* worker state; never invent progress or artistic QA."""
        if type(include_artifacts) is not bool:
            raise BodyCommandRejected("Artifact flag must be boolean")
        job = self._coordinator.inspect(job_id)
        if not isinstance(job, dict):
            raise RuntimeError("Worker did not return observed job state")
        progress = job.get("actual_tool_progress")
        if not isinstance(progress, dict):
            progress = {"observed_tool_states": [],
                        "tool_progress_is_actual_sqlite": False}
        states = progress.get("observed_tool_states", [])
        if not isinstance(states, list):
            states = []
        result = job.get("result") or {}
        if not isinstance(result, dict):
            result = {}
        output = {"protocol": self.VERSION,
                  "job_id": job.get("job_id"), "status": job.get("status"),
                  "attempts": job.get("attempts"),
                  "requested_action": job.get("requested_action"),
                  "tool_states": states[:500],
                  "tool_progress_is_actual_sqlite":
                      progress.get("tool_progress_is_actual_sqlite") is True,
                  "execution_outcome": result.get("status"),
                  "movie_verified": result.get("movie_delivered") is True,
                  "technical_error": self._bounded_text(
                      result.get("message", "")),
                  "artistic_approval": "not_inferred"}
        if include_artifacts:
            media = self._coordinator.list_media(job_id)
            entries = media.get("assets", [])
            if not isinstance(entries, list):
                raise RuntimeError("Worker returned malformed media inventory")
            output["artifacts"] = [{
                "path": a.get("path"), "sha256": a.get("sha256"),
                "bytes": a.get("bytes"),
                "accepted_as_finished_film": False
            } for a in entries[:200] if isinstance(a, dict)]
            output["more_artifacts"] = len(entries) > 200
        return output

    def command(self, action, arguments):
        """Only host-authorized mutations can cross into the real worker.

        The owner-host's BodyAuthority is NOT part of model arguments. No
        direct arbitrary tool execution or arbitrary external network calls.
        """
        if not isinstance(action, str) or action not in (
                "submit", "pause", "cancel", "resume", "retry"):
            raise BodyCommandRejected("Unknown body mutation")
        if action not in self._authority.operations:
            raise PermissionError("Host has not authorized this body operation")
        if not isinstance(arguments, dict):
            raise BodyCommandRejected("Body command arguments must be an object")
        expected = {"film_ir", "workspace_id"} if action == "submit" else {"job_id"}
        if set(arguments) != expected:
            raise BodyCommandRejected("Malformed or excessive body command fields")
        if action == "submit":
            film_ir = arguments["film_ir"]
            if not isinstance(film_ir, dict):
                raise BodyCommandRejected("Film IR must be a structured object")
            tools = self._catalog().executable_ids(
                allowed_access=self._authority.tool_access)
            check = validate_film_ir(
                film_ir, installed_tool_ids=tools,
                fact_ids=set(self._authority.fact_ids))
            if not check.render_ready:
                raise BodyCommandRejected(
                    "Original film cannot be scheduled: " +
                    "; ".join(check.errors + check.warnings))
            # Renderer execution uses the project's pre-existing authenticated
            # persistent queue, durable graph and media-verification gates.
            return self._coordinator.submit(
                film_ir, workspace_id=arguments["workspace_id"])
        job_id = arguments["job_id"]
        if action in ("pause", "cancel"):
            return self._coordinator.request_control(job_id, action)
        return self._coordinator.retry_job(job_id, resume=action == "resume")

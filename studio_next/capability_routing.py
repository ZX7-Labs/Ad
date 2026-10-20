"""Creative intent first: discover capable, *actually runnable* engine routes.

This planner does not decide visual style or lower artistic requirements. The
Director lists exact required capabilities and any artistically approved
alternatives. Registered, rights-reviewed and permissioned tools are then
selected. An unavailable 3D request remains a 3D request, not a 2D substitute.

No video or artistic acceptance is inferred from a successful route.
"""
from dataclasses import dataclass, field
from .contracts import ToolSpec
from .registry import ToolCatalog

@dataclass(frozen=True)
class Route:
    requirement_id: str
    shot_ids: tuple[str, ...]
    capabilities: tuple[str, ...]
    tool_ids: tuple[str, ...]
    alternative_index: int

@dataclass(frozen=True)
class RoutingReport:
    executable: bool
    routes: tuple[Route, ...] = ()
    unresolved: tuple[dict, ...] = ()
    claim: str = "Routing is a permission check, not a video or a creative approval."


def _check_ids(values, *, label):
    if not isinstance(values, list) or not values or any(
        not isinstance(x, str) or not x.strip() for x in values
    ) or len(values) != len(set(values)):
        raise ValueError(label + " must be nonempty, distinct strings")
    return tuple(values)


def resolve_routes(film: dict, catalog: ToolCatalog, *,
                   allowed_access=frozenset({"read"}),
                   approved_licenses=frozenset({"MIT", "Apache-2.0", "GPL-3.0-or-later"}),
                   trusted_free_tool_ids=frozenset()):
    """Find a tool set for each creative requirement, retaining its exact intent.

    Film requirements:
      [{"id":"render-deep", "shot_ids":["intro"],
        "alternatives":[["visual.true_3d","camera.3d"],
                        ["visual.licensed_3d_footage"]]}]
    Alternatives are authored/approved by the Director; this function never
    inserts one. Most expressive tools may expose several registered operations.
    """
    if not isinstance(film, dict) or not isinstance(catalog, ToolCatalog):
        raise TypeError("Film and registered tool catalog required")
    shots = film.get("shots")
    if not isinstance(shots, list) or not shots:
        raise ValueError("Film needs actual authored shots")
    shot_ids = _check_ids([s.get("id") for s in shots if isinstance(s, dict)],
                          label="Shot IDs")
    if len(shot_ids) != len(shots):
        raise ValueError("Malformed film shots")
    requirements = film.get("production_requirements")
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("Explicit creative production requirements are needed")
    if not isinstance(trusted_free_tool_ids, (set, frozenset)):
        raise TypeError("Trusted no-cost tool IDs are required")
    active_ids = catalog.executable_ids(allowed_access)
    allowed_licenses = set(approved_licenses)
    candidates = [
        meta for meta in catalog.discover()
        if meta["id"] in active_ids and meta["id"] in trusted_free_tool_ids
        and meta["license"] in allowed_licenses
    ]
    routes = []
    unresolved = []
    known_ids = set()
    for req in requirements:
        if not isinstance(req, dict) or set(req) != {"id", "shot_ids", "alternatives"}:
            raise ValueError("Invalid typed creative requirement")
        ident = req["id"]
        if not isinstance(ident, str) or not ident.strip() or ident in known_ids:
            raise ValueError("Requirement ID must be unique")
        known_ids.add(ident)
        mapped = _check_ids(req["shot_ids"], label="Requirement shot IDs")
        if not set(mapped).issubset(shot_ids):
            raise ValueError("Requirement references a nonexistent shot")
        alternatives = req["alternatives"]
        if not isinstance(alternatives, list) or not alternatives:
            raise ValueError("Director must explicitly supply creative alternatives")
        chosen = None
        missing_options = []
        for alt_index, option in enumerate(alternatives):
            capabilities = _check_ids(option, label="Alternative capabilities")
            selected = []
            missing = []
            for cap in capabilities:
                matches = [m for m in candidates if m["capability"] == cap]
                if not matches:
                    missing.append(cap)
                else:
                    # Choose deterministically among equivalent installed tools,
                    # not between different unapproved creative concepts.
                    selected.append(sorted(m["id"] for m in matches)[0])
            if missing:
                missing_options.append({"alternative_index": alt_index,
                                        "missing_capabilities": missing})
                continue
            chosen = Route(ident, mapped, capabilities,
                           tuple(dict.fromkeys(selected)), alt_index)
            break
        if chosen is None:
            unresolved.append({"id": ident, "shot_ids": list(mapped),
                               "unmet_options": missing_options})
        else:
            routes.append(chosen)
    return RoutingReport(not unresolved, tuple(routes), tuple(unresolved))

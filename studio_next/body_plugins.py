"""On-demand administrator-installed creative body extensions.

The creative artist sees only concise real installed capabilities via the
existing tool catalog. Third-party application packages explicitly opt in
through Python entry points and a separate host allow-list. Merely including
the name in a model response never imports or installs an executable.

Python plugins are TRUSTED host code (not a sandbox); operators must install
and audit them. Access grants are still enforced by ToolCatalog. Capabilities
and genres are NOT hardcoded here.
"""
from __future__ import annotations

import os
import re
from importlib.metadata import entry_points

from .contracts import ToolSpec

_NAME=re.compile(r"^[a-z][a-z0-9_.-]{1,100}$")


def discover_enabled_body_plugins(*,approved=None,entry_source=None):
    configured=approved if approved is not None else os.environ.get(
        "ZX7_ENABLED_BODY_PLUGINS","").split(",")
    allow={x.strip() for x in configured if isinstance(x,str) and x.strip()}
    if not allow:
        return []
    for identity in allow:
        if not _NAME.fullmatch(identity) or identity.startswith("."):
            raise ValueError("Unsafe administrative body plugin ID")
    records=entry_source if entry_source is not None else entry_points()
    if hasattr(records,"select"):
        candidates=records.select(group="zx7.body_operations")
    elif isinstance(records,dict):
        candidates=records.get("zx7.body_operations",[])
    else:
        candidates=records  # trusted explicit iterable in tests or deployment
    found={}
    for plugin in candidates:
        if plugin.name not in allow:
            continue
        if plugin.name in found:
            raise ValueError("Duplicate installed professional tool implementation")
        adapter=plugin.load()()
        spec=adapter.spec
        if not isinstance(spec,ToolSpec) or spec.tool_id!=plugin.name:
            raise ValueError("External body provider returned a false tool identity")
        if not callable(getattr(adapter,"run",None)) or not callable(
                getattr(adapter,"probe",None)):
            raise ValueError("Enabled creative application has no tested execution boundary")
        if not callable(getattr(adapter,"material_fingerprint",None)):
            raise ValueError("Enabled plugin cannot prove original source material bytes")
        operational=adapter.probe()
        if type(operational) is not bool:
            raise ValueError("Creative plugin operational check must return bool")
        if spec.access=="paid":
            # Paid resources require an independent explicit access grant later.
            # Presence alone does not purchase anything.
            pass
        version=getattr(adapter,"revision",None)
        if not isinstance(version,str) or len(version)<8:
            raise ValueError("Production plugin lacks a stable code/adapter revision")
        safe_retry=getattr(adapter,"idempotent",None)
        if type(safe_retry) is not bool:
            raise ValueError("Installed plugin retry safety must be explicit")
        found[plugin.name]=(spec,adapter.run if operational else None,
                            safe_retry,version,operational,adapter.material_fingerprint)
    missing=allow-set(found)
    if missing:
        raise ValueError("Admin enabled missing/uninstalled body plugins: "+", ".join(sorted(missing)))
    return list(found.values())

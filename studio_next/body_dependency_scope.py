"""Conservative dependency scoping for non-destructive original cinema.

A film artist can declare precise shots and media dependencies for a stage.
Tool input files are always measured separately, and upstream stage output
digests flow through the actual DAG. Unscoped nodes conservatively depend on
every project asset and shot; an explicitly scoped node should NOT re-render
because a different independent shot acquired a new asset.

This code chooses NO visual style, shot count, frame rate, voice or renderer.
"""
from __future__ import annotations


def select_verified_node_assets(all_assets, node, related_shots):
    if not isinstance(all_assets,list) or not isinstance(node,dict):
        raise ValueError("Trusted original film asset graph required")
    by_id={asset["id"]:asset for asset in all_assets}
    node_scope=node.get("asset_refs")
    shot_scope=node.get("shot_refs")
    if shot_scope is None and node_scope is None:
        return all_assets
    # A shot scope asserts a strictly limited portion of the original film,
    # but its referenced sources must still be dependencies, even if the
    # artist forgot to repeat them on the stage.
    selected=set()
    if shot_scope is not None:
        for shot in related_shots:
            selected.update(shot.get("asset_refs",[]))
    if node_scope is not None:
        selected.update(node_scope)
    if shot_scope is None and node_scope is not None:
        # Only a declared asset scope does not constrain the artistic shots;
        # no source other than a declared reference may be ignored.
        pass
    unknown=selected-set(by_id)
    if unknown:
        raise ValueError("Unknown explicitly scoped original asset identity")
    return [asset for asset in all_assets if asset["id"] in selected]

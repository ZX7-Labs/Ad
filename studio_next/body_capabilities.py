"""Short, live, queryable brain-to-body capability interface.

The artist doesn't receive a giant MD manual listing its hands and feet.
`list_operational_tools()` returns compact measured installed operations.
`describe_operation(id)` returns a precise permissioned schema only when
the film intelligence needs a specific tool. Tool registration/provenance,
actual CPU/GPU capacity and installed plugins are discovered at call time.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .body_integration import body_catalog
from .creative_tool_registry import creative_tool_inventory
from .generative_video_providers import discover_local_generators


def operational_tool_summary(workspace,*,keywords=None):
    specs=body_catalog(workspace).discover()
    permitted=[x for x in specs if x["status"]=="installed"]
    words=[v.strip().lower() for v in (keywords or []) if isinstance(v,str) and v.strip()]
    def matching(item):
        if not words:return True
        corpus=" ".join(str(item.get(k,"")) for k in (
            "id","capability","description")).lower()
        return all(w in corpus for w in words)
    # Fixed body contract concerns only tool semantics, NOT editing genre/style.
    return [{"tool_id":x["id"],"capability":x["capability"],
             "access":x["access"],"status":"genuinely_installed"}
            for x in permitted if matching(x)]


def explain_operational_tool(workspace,tool_id):
    # Show full schema for a selected tool only (no 40k MD prompt).
    if not isinstance(tool_id,str) or not tool_id:
        raise ValueError("Exact installed tool id needed")
    for tool in body_catalog(workspace).discover():
        if tool["id"]==tool_id:
            if tool["status"]!="installed":
                return {"status":"needs_setup","tool_id":tool_id,
                        "reason":"Real executable dependency unavailable"}
            return {"status":"ready_for_execution_trial",
                    "tool_id":tool_id,
                    "operation_schema":tool["schema"],
                    "capability":tool["capability"],
                    "access":tool["access"],
                    "limits":tool["limitations"],
                    "declared_license":tool["license"],
                    "no_artistic_preset":True}
    raise ValueError("Tool is not registered in actual creative body")


def concise_body_status(workspace):
    tools=operational_tool_summary(workspace)
    physical=creative_tool_inventory()
    generators=discover_local_generators()
    gpu_ready=[c["id"] for c in generators["video_generation_options"]
               if c["ready_for_independent_execution_trial"]]
    return {"connected_executable_tool_count":len(tools),
        "registered_genuine_operations":tools,
        "installed_creative_app_ids":[a["tool_id"]
          for a in physical["actual_installed_tools"]],
        "third_party_apps_present_but_not_all_wired":[a["tool_id"] for a in
           physical["actual_installed_tools"] if not a["can_render_in_zx7_now"]],
        "physically_enabled_generators":gpu_ready,
        "one_model_can_discover_and_choose_without_reading_documentation":True,
        "claimed_complete_premium_studio":False,
        "claim":"Real tool interface; successful movie depends on source art and tested runtime"}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace",type=Path,required=True)
    p.add_argument("--tool-id")
    p.add_argument("--keyword",action="append")
    p.add_argument("--out",type=Path)
    x=p.parse_args()
    if x.tool_id:
        result=explain_operational_tool(x.workspace,x.tool_id)
    elif x.keyword:
        result={"tools":operational_tool_summary(x.workspace,keywords=x.keyword)}
    else:
        result=concise_body_status(x.workspace)
    if x.out:
        x.out.parent.mkdir(parents=True,exist_ok=True)
        x.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":main()

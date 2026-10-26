"""Reproducible whole-Git-tree source and source-format audit for ZX7.

This enumerates EVERY tracked file and validates parseable code/config. It is
an inventory and basic integrity audit, not a cinematic or security release.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path


_REVIEW_CALLS=frozenset({
    "os.replace","os.rename","os.link","os.unlink","os.remove",
    "shutil.copyfile","shutil.copy2","shutil.rmtree",
    "subprocess.run","subprocess.Popen","subprocess.call",
    "eval","exec",
})


def _call_name(expr):
    if isinstance(expr,ast.Name):
        return expr.id
    if isinstance(expr,ast.Attribute):
        parent=_call_name(expr.value)
        return (parent+"." if parent else "")+expr.attr
    return ""


def _risky_python_sites(tree,path):
    sites=[]
    for node in ast.walk(tree):
        if not isinstance(node,ast.Call):
            continue
        name=_call_name(node.func)
        shell_true=any(
            kw.arg=="shell" and isinstance(kw.value,ast.Constant)
            and kw.value.value is True for kw in node.keywords)
        if name in _REVIEW_CALLS or (
                name.endswith((".unlink",".write_text",".write_bytes"))
                and name not in _REVIEW_CALLS) or shell_true:
            sites.append({"path":path,"line":node.lineno,
                          "call":name,"shell_true":shell_true,
                          "independently_security_reviewed":False})
    return sorted(sites,key=lambda item:item["line"])


def audit(root, names):
    import yaml
    files=[]
    blocked=[]
    risky_sites=[]
    summary={"python":0,"json":0,"toml":0,"yaml":0,"other":0}
    for name in sorted(set(names)):
        relative=Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            blocked.append({"path":name,"reason":"untrusted indexed path"})
            continue
        path=root/relative
        if path.is_symlink() or not path.is_file():
            blocked.append({"path":name,"reason":"source is not a regular tracked file"})
            continue
        data=path.read_bytes()
        files.append({"path":name,"bytes":len(data),
                      "sha256":hashlib.sha256(data).hexdigest()})
        typ=path.suffix.lstrip(".").lower()
        typ=typ if typ in ("py","json","toml","yaml","yml") else "other"
        summary[{"py":"python","yml":"yaml"}.get(typ,typ)]+=1
        try:
            if typ=="py":
                tree=ast.parse(data.decode("utf-8"),filename=name)
                compile(tree,name,"exec")
                risky_sites.extend(_risky_python_sites(tree,name))
            elif typ=="json":
                json.loads(data)
            elif typ=="toml":
                tomllib.loads(data.decode("utf-8"))
            elif typ in ("yml","yaml"):
                obj=yaml.safe_load(data)
                if not isinstance(obj,dict):
                    raise ValueError("Expected YAML document mapping")
        except Exception as exc:
            blocked.append({"path":name,"reason":type(exc).__name__,
                            "detail":str(exc)[:180]})
    if len(names)!=len(set(names)):
        blocked.append({"reason":"duplicate tracked source path"})
    return {"schema":1,"scope":"every tracked file","files":files,
            "counts":summary,"total_file_count":len(files),
            "static_source_change_sites":sorted(
                risky_sites,key=lambda row:(row["path"],row["line"])),
            "static_source_change_sites_are_candidates_not_verified_flaws":True,
            "blocking_source_format_errors":blocked,
            "security_manual_review_complete":False,
            "film_release_production_approved":False,
            "all_twelve_quality_gates_complete":False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    options=p.parse_args(argv)
    root=options.root.resolve()
    names=subprocess.run(["git","-C",str(root),"ls-files","-z"],
                         capture_output=True,check=True,timeout=30).stdout.decode("utf-8")
    report=audit(root,[x for x in names.split("\0") if x])
    report["git_commit"]=subprocess.run(
        ["git","-C",str(root),"rev-parse","HEAD"],
        capture_output=True,text=True,check=True,timeout=15).stdout.strip()
    target=options.out.resolve()
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2,sort_keys=True,
                                 ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"git_commit":report["git_commit"],
       "sources":report["total_file_count"],"counts":report["counts"],
       "risk_sites":len(report["static_source_change_sites"]),
       "format_blockers":report["blocking_source_format_errors"],
       "full_production_approved":False}))
    return 1 if report["blocking_source_format_errors"] else 0


if __name__=="__main__":
    sys.exit(main())

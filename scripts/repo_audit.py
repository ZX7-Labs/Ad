"""Reproducible whole-Git-tree source and source-format audit for ZX7.

This enumerates EVERY tracked file, including initialized pinned submodule
sources, and validates parseable code/config. Gitlinks are recorded separately
from regular-file SHA256 digests. It is
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


def _git(root,*args):
    return subprocess.run(["git","-C",str(root),*args],capture_output=True,
                          check=True,timeout=30).stdout.decode("utf-8")


def _index(root):
    """Read modes from this repository's index, never an enclosing repository."""
    try:
        top=Path(_git(root,"rev-parse","--show-toplevel").strip()).resolve()
    except subprocess.CalledProcessError:
        return {}
    if top!=root.resolve():
        return {}
    entries={}
    for entry in _git(root,"ls-files","--stage","-z").split("\0"):
        if entry:
            metadata,name=entry.split("\t",1)
            mode,oid,stage=metadata.split()
            entries[name]=(mode,oid,stage)
    return entries


def _safe_path(root,relative):
    path=root
    for part in relative.parts:
        path=path/part
        if path.is_symlink():
            return False
    return path.resolve().is_relative_to(root.resolve())


def _pinned_submodule(root,name,pin,index):
    """Verify a registered checkout before following its own tracked sources."""
    modules=root/".gitmodules"
    if not modules.is_file() or modules.is_symlink() or \
            index.get(".gitmodules",("",))[0] not in ("100644","100755"):
        raise ValueError("gitlink has no tracked .gitmodules registration")
    registrations=_git(root,"config","--file",str(modules),"--null",
                       "--get-regexp",r"^submodule\..*\.path$")
    registered=[entry.split("\n",1)[1] for entry in registrations.split("\0") if entry]
    if registered.count(name)!=1:
        raise ValueError("gitlink must have exactly one .gitmodules registration")
    path=root/name
    if not path.is_dir() or not (path/".git").exists() or (path/".git").is_symlink():
        raise ValueError("pinned submodule is not initialized")
    top=Path(_git(path,"rev-parse","--show-toplevel").strip()).resolve()
    if top!=path.resolve():
        raise ValueError("submodule must have its own exact repository top-level")
    head=_git(path,"rev-parse","HEAD").strip()
    if head!=pin:
        raise ValueError("submodule HEAD does not match indexed gitlink pin")
    # Index flags can hide edits from ordinary Git diff checks. Fail closed
    # rather than treating assume-unchanged or sparse files as verified source.
    flags=_git(path,"ls-files","-v","-z").split("\0")
    if any(row and (row[0].islower() or row[0]=="S") for row in flags):
        raise ValueError("submodule has hidden or sparse tracked-source index flags")
    _git(path,"diff","--quiet","--ignore-submodules=none","HEAD","--")
    return {"path":name,"kind":"gitlink","git_mode":"160000",
            "commit":pin,"checked_out_commit":head,"tracked_source_clean":True}


def audit(root, names):
    import yaml
    root=Path(root).resolve()
    index=_index(root)
    files=[]
    pins=[]
    blocked=[]
    risky_sites=[]
    summary={"python":0,"json":0,"toml":0,"yaml":0,"other":0}
    for name in sorted(set(names)):
        relative=Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            blocked.append({"path":name,"reason":"untrusted indexed path"})
            continue
        path=root/relative
        if not _safe_path(root,relative):
            blocked.append({"path":name,"reason":"untrusted indexed source path"})
            continue
        mode,pin,stage=index.get(name,(None,None,None))
        if mode=="160000":
            try:
                if stage!="0":
                    raise ValueError("gitlink has unresolved index stages")
                record=_pinned_submodule(root,name,pin,index)
                child_index=_index(path)
                nested=audit(path,list(child_index))
            except (ValueError,OSError,subprocess.SubprocessError) as exc:
                blocked.append({"path":name,"reason":"pinned source verification failed",
                                "detail":str(exc)[:180]})
                continue
            pins.append(record)
            for key,target in (("files",files),("pinned_sources",pins),
                               ("static_source_change_sites",risky_sites),
                               ("blocking_source_format_errors",blocked)):
                for row in nested[key]:
                    target.append({**row,"path":name+"/"+row["path"]
                                   if "path" in row else name})
            for key,count in nested["counts"].items():
                summary[key]+=count
            continue
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
            "pinned_sources":pins,
            "pinned_source_scope":"initialized registered gitlinks and their tracked sources",
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

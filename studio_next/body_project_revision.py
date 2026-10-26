"""Atomic edits to creative JSON data, never BODY code or installed capabilities.

JSON Pointer and add/remove/replace/test patch operations create a new document.
The caller validates the final native schema and preserves the immutable source.
"""
from __future__ import annotations
import copy
import json
import re


def pointer_parts(pointer):
    if not isinstance(pointer,str) or len(pointer)>4096:raise ValueError("Project pointer must be bounded text")
    if pointer=="":return []
    if not pointer.startswith("/"):raise ValueError("Project pointer must start with /")
    parts=pointer[1:].split("/")
    if len(parts)>64 or any(re.search(r"~(?![01])",part) for part in parts):raise ValueError("Invalid or deep JSON pointer")
    return [part.replace("~1","/").replace("~0","~") for part in parts]


def _index(part,size,*,inserting=False):
    if inserting and part=="-":return size
    if not re.fullmatch(r"0|[1-9][0-9]*",part) or len(part)>12:raise ValueError("Array pointer requires exact nonnegative index")
    index=int(part);maximum=size if inserting else size-1
    if index>maximum:raise ValueError("Array pointer is out of range")
    return index


def _child(value,part):
    if isinstance(value,dict):
        if part not in value:raise ValueError("Project pointer names missing field")
        return value[part]
    if isinstance(value,list):return value[_index(part,len(value))]
    raise ValueError("Project pointer traverses a scalar")


def selected_value(document,pointer):
    value=document
    for part in pointer_parts(pointer):value=_child(value,part)
    return copy.deepcopy(value)


def _equal_json(a,b):
    if type(a) in (int,float) and type(b) in (int,float):return a==b
    if type(a) is not type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(_equal_json(a[k],b[k]) for k in a)
    if isinstance(a,list):return len(a)==len(b) and all(_equal_json(x,y) for x,y in zip(a,b))
    return a==b


def revise_document(document,operations):
    if not isinstance(operations,list) or not 1<=len(operations)<=512:raise ValueError("Revision requires 1..512 explicit operations")
    try:
        encoded=json.dumps(operations,allow_nan=False)
        if len(encoded.encode())>262144:raise ValueError("Revision exceeds host document budget")
        changes=json.loads(encoded);result=json.loads(json.dumps(document,allow_nan=False))
    except (TypeError,OverflowError,RecursionError) as exc:raise ValueError("Revision is not bounded finite JSON") from exc
    for item in changes:
        if not isinstance(item,dict) or item.get("op") not in ("add","remove","replace","test"):
            raise ValueError("Unknown creative document edit operation")
        op=item["op"]
        if set(item)!=({"op","path"} if op=="remove" else {"op","path","value"}):raise ValueError("Revision fields do not match contract")
        parts=pointer_parts(item["path"])
        if op=="test":
            if not _equal_json(selected_value(result,item["path"]),item["value"]):raise ValueError("Creative document edit precondition failed")
            continue
        if not parts:
            if op=="remove":raise ValueError("Cannot remove the whole creative document")
            result=copy.deepcopy(item["value"]);continue
        parent=result
        for part in parts[:-1]:parent=_child(parent,part)
        last=parts[-1]
        if isinstance(parent,dict):
            if op in ("remove","replace") and last not in parent:raise ValueError("Revision target does not exist")
            if op=="remove":del parent[last]
            else:parent[last]=copy.deepcopy(item["value"])
        elif isinstance(parent,list):
            index=_index(last,len(parent),inserting=op=="add")
            if op=="add":parent.insert(index,copy.deepcopy(item["value"]))
            elif op=="remove":parent.pop(index)
            else:parent[index]=copy.deepcopy(item["value"])
        else:raise ValueError("Revision target parent is scalar")
    if not isinstance(result,dict):raise ValueError("Creative document root must remain an object")
    return result

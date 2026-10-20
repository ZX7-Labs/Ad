#!/usr/bin/env python3
"""Convert one owner-submitted GitHub Issue Form into a safe structured video brief."""
import json,re,sys
from pathlib import Path
raw=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
issue=raw.get("issue") or {}
body=issue.get("body") or ""
allowed=["Product name","What are you promoting?","Who is this for?",
         "What's the ONE most important benefit?","Any slogan or style direction? (optional)",
         "What should viewers do at the end?"]
sections={}
for m in re.finditer(r"(?ms)^### ([^\n]+)\n\n(.*?)(?=\n### |\Z)",body):
    sections[m.group(1).strip()]=m.group(2).strip()
if not all(sections.get(k) for k in (allowed[0],allowed[1],allowed[2],allowed[3],allowed[5])):
    raise ValueError("Missing required AD Studio issue form questions")
def clean(s,n=110):
    s=re.sub(r"[\r\n\t]+"," ",str(s or ""))
    s=re.sub(r"\s+"," ",s).strip()
    return s[:n]
cat=clean(sections[allowed[1]],25).lower()
if cat not in ("software","physical","service"):
    raise ValueError("Unsupported product category")
brief={
    "product":clean(sections[allowed[0]],46),
    "category":cat,
    "audience":clean(sections[allowed[2]],85),
    "benefit":clean(sections[allowed[3]],105),
    "tagline":clean(sections.get(allowed[4],""),90),
    "cta":clean(sections[allowed[5]],60)
}
assert all(brief[k] for k in ("product","category","audience","benefit","cta"))
path=Path("output/input_brief.json");path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(brief,indent=2),encoding="utf-8")
print("Validated brief for:",brief["product"],"category",brief["category"])

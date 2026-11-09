#!/usr/bin/env python3
"""Project existing IDTSPE 2D Target Modules + Units to read-only, NOT-SELECTED R-D template graphs.

This is a *source-preserving projection*, not an edit of IDTSPE methodology or an
acceptance of any module in a real project. Full source Markdown stays embedded
byte-for-byte as decoded UTF-8 in every graph's sourceMarkdown.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PROFILE = Path("/workspace/repos/obs-planning-docs/planning/documentation/idtspe-methodology/active/profiles/visual-production-2d")
REGISTRY = PROFILE / "registries/TARGET-MODULE-REGISTRY.md"
GRAPH_ROOT = BASE / "graphs" / "2d"

def ensure(condition: bool, msg: str):
    if not condition:
        raise ValueError(msg)

def section(markdown: str, name: str) -> str:
    m = re.search(r"(?m)^## " + re.escape(name) + r"\s*$", markdown)
    if not m:
        return ""
    stop = re.search(r"(?m)^## ", markdown[m.end():])
    return markdown[m.start(): m.end() + stop.start()] if stop else markdown[m.start():]

def literal(markdown: str, label: str) -> str:
    m = re.search(r"(?m)^" + re.escape(label) + r":\s*(.+)$", markdown)
    return m.group(1).strip() if m else ""

def plain_markdown_link(s: str) -> str:
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", s).strip()

def rows_for_units(s: str):
    inventory = section(s, "Module-defined Unit Inventory")
    ensure(bool(inventory), "Module-defined Unit Inventory missing")
    items = []
    for row in inventory.splitlines():
        m = re.match(r"^\|\s*`(RU-[A-Za-z0-9-]+)`\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$", row)
        if not m:
            continue
        unit_id, title, responsibility = m.groups()
        items.append(dict(id=unit_id, title=plain_markdown_link(title),
                          inventoryTitle=title, responsibility=responsibility,
                          inventoryRow=row))
    ensure(bool(items), "No Units found")
    ensure(len(set(x["id"] for x in items)) == len(items), "duplicate Unit ID")
    return items, inventory

def read_unit_guidance(s: str, items):
    block = section(s, "Unit-specific Guidance")
    ensure(bool(block), "Unit-specific Guidance missing")
    anchors = []
    for m in re.finditer(r"(?m)^<a id=\"([^\"]+)\"></a>\s*\n^### ([^\n]+)\s*$", block):
        anchors.append((m.group(1), m.group(2).strip(), m.start()))
    result = {}
    for i, (anchor, heading, start) in enumerate(anchors):
        unit_block = block[start:anchors[i + 1][2] if i + 1 < len(anchors) else len(block)]
        # Every Unit's exact source definition is retained.
        result[anchor.lower()] = dict(anchor=anchor, heading=heading,
                                      guidanceMarkdown=unit_block.rstrip("\n"))
    for u in items:
        ensure(u["id"].lower() in result, f"Missing Unit-specific Guidance: {u['id']}")
        ensure(result[u["id"].lower()]["heading"] == u["title"],
               f"Unit heading mismatch: {u['id']}")
    ensure(len(result) == len(items), "Unmatched Unit Guidance sections")
    return result

def registry_entries(s: str):
    entries = {}
    for row in s.splitlines():
        m = re.match(
            r"^\|\s*(\d+)\s*\|\s*\[([^\]]+)\]\(([^)]*)\)\s*\|\s*`(TM-2D-[^\x60]+)`\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*$",
            row)
        if m:
            depth, label, link, ident, roles, usage = m.groups()
            entries[ident] = dict(depth=int(depth), label=label, originalLink=link,
                                  roles=roles.strip(), usage=usage.strip(),
                                  inventoryRow=row)
    return entries

def construct(path: Path, entry):
    raw = path.read_bytes().decode("utf-8")  # Does NOT normalize original CRLF.
    s = raw.replace("\r\n", "\n")
    mid = literal(s, "Module ID").strip("`")
    ensure(mid == path.stem and mid == entry["id"], f"Module ID mismatch: {path}")
    ensure("Status: active profile module" in s, "Unexpected status: " + mid)
    units, inventory = rows_for_units(s)
    guidance = read_unit_guidance(s, units)
    parts = {m.group(1):m.group(0) for m in re.finditer(
        r"(?ms)^## ([^\n]+)\n.*?(?=^## |\Z)",s)}
    # preserve sections as exact method text, including cross-Unit guidance,
    # formation/scope gates, workflows, validators, handoff, file contracts.
    unrecognized = [u for u in units if u["id"].lower() not in guidance]
    ensure(not unrecognized, "Unmatched Units")
    purpose = section(s, "Purpose").strip()
    target_result = section(s, "Target Step Result").strip()
    root_id = "TEMPLATE-R-TARGET-RESULT"
    n = [
      dict(id=root_id,kind="requirement",title=entry["label"]+" — получить целевой результат",
        templateRole="target-goal-placeholder",status="not-instantiated",
        description="Условная цель для демонстрации заранее подготовленного разбиения. Не является фактическим Requirement проекта.\n\n"+purpose+"\n\n"+target_result,
        source=path.as_posix()),
      dict(id=mid,kind="decision",title="Готовое разбиение: "+entry["label"],
        status="reusable-unselected",selected=False,
        templateRole="target-module-prepared-decomposition",source=path.as_posix(),
        description="Переиспользуемая заготовка Target Module, не принятое Decision.\n\n"
          +purpose+"\n\n"+target_result+"\n\n"+inventory.strip(),
        entryPoint=literal(s,"Entry Point").strip("`"),
        supportedRoles=literal(s,"Supported Roles"),moduleStatus=literal(s,"Status"),
        targetModuleId=mid,sourceSections=list(parts),
        fullModuleMarkdown=raw)
    ]
    e = [dict(id="TEMPLATE-E-000",type="DRIVES", **{"from":root_id},to=mid,
      templateOnly=True,meaning="Этот заранее подготовленный способ МОЖЕТ быть выбран для подходящей цели; пока он не принят.")]
    for i, u in enumerate(units,1):
        unit_id = u["id"]
        exact = guidance[unit_id.lower()]
        checkpoint = "\n".join(line for line in section(s,"Unit Checkpoint Map").splitlines()
                               if unit_id in line)
        n.append(dict(id=unit_id,kind="requirement",
          title=u["title"],templateRole="prepared-unit-definition",
          status="not-instantiated",selected=False,source=path.as_posix()+"#"+exact["anchor"],
          description="Ответственность (из исходного Unit Inventory):\n"+u["responsibility"]+
                      "\n\nГотовая Unit-specific Guidance:\n"+exact["guidanceMarkdown"],
          boundedResponsibility=u["responsibility"],
          inventoryRow=u["inventoryRow"],guidanceMarkdown=exact["guidanceMarkdown"],
          sourceAnchor=exact["anchor"],unitCheckpointMarkdown=checkpoint))
        e.append(dict(id=f"TEMPLATE-E-{2*i-1:03d}",type="INTRODUCES",
          **{"from":mid},to=unit_id,parent=root_id,templateOnly=True,
          meaning="Готовая Unit Definition в полном составе Target Module; не instantiated."))
        # In source some Units have prepared guidance, but no explicit
        # nested requirement inventory. Represent guidance as unselected D
        # WITHOUT inventing sub-Requirements.
        did="TEMPLATE-D-"+unit_id
        n.append(dict(id=did,kind="decision",status="reusable-unselected",
          templateRole="unit-prepared-guidance",selected=False,
          title="Готовый способ проработки: "+u["title"],
          description=exact["guidanceMarkdown"],
          source=path.as_posix()+"#"+exact["anchor"],
          sourceUnitId=unit_id,
          explicitSubrequirements=False,
          note="Source defines Unit guidance; no explicit nested R inventory is declared here."))
        e.append(dict(id=f"TEMPLATE-E-{2*i:03d}",type="DRIVES",
          **{"from":unit_id},to=did,templateOnly=True,
          meaning="Заготовка способа проработки Unit — не выбор проекта и не готовый результат."))
    slug="template-"+mid.lower().replace("-","-")
    # Keep exact complete original text, not only interpreted graph fragments.
    graph = dict(schemaVersion=1,id=slug,title="Заготовка 2D · "+entry["label"],
      revision=2,readOnly=True,templateOnly=True,exampleOnly=False,selected=False,
      planningScale="module", identitySpace="prepared:"+mid,
      rootRequirementId=root_id,
      templateKind="prebuilt-target-module-and-unit-methods",
      sourceMethodology="IDTSPE / 2D Visual Production (active)",
      sourceDocument=path.as_posix(),
      sourceContentSHA256=hashlib.sha256(path.read_bytes()).hexdigest(),
      sourceMarkdown=raw,
      sourceSections=list(parts),
      originalSections=parts,
      sourceRegistry=REGISTRY.as_posix(),
      sourceRegistryEntry=entry,
      originalTargetModuleId=mid,
      targetModuleEntryPoint=literal(s,"Entry Point").strip("`"),
      originalStatus=literal(s,"Status"),
      originalUnitInventory=inventory,
      unitCount=len(units),
      unitIds=[u["id"] for u in units],
      conversionNote=("Проекция исходной reusable-модели, не реальный выбор. "
         "Target Module разложен на исходные Units; Unit-specific Guidance показана как "
         "готовый способ проработки Unit, не принятый и не обязательно содержащий собственные под-R. "
         "Весь исходный Markdown (включая таблицы, formation gates, cross-Unit правила, validators, "
         "artifact contracts, ссылки) сохранён дословно в sourceMarkdown."),
      coverage=(f"{mid}. Полный исходный Unit Inventory: {len(units)}. "
        "Не выбрано и не применено. Оригинал без потери текста сохранён внутри графа."),
      nodes=n,edges=e,events=[])
    graph["preparedModule"] = dict(id=mid, version=graph["sourceContentSHA256"],
        goalRequirementId=root_id, methodDecisionId=mid, childRequirementIds=graph["unitIds"],
        applicability=purpose, successCriteria=target_result)
    ensure(len(graph["nodes"])==2+2*len(units),"Wrong node count")
    ensure(len(graph["edges"])==1+2*len(units),"Wrong edge count")
    ensure(len([x for x in n if x.get("kind")=="requirement" and x["id"].startswith("RU-")])==len(units),"Missing Unit")
    return graph

def unit_graphs(graph):
    """Each old Unit has its own graph; parent is the single owner of its R."""
    children = []
    unit_ids = set(graph["unitIds"])
    for uid in graph["unitIds"]:
        r = next(n for n in graph["nodes"] if n["id"] == uid)
        d = next(n for n in graph["nodes"] if n["id"] == "TEMPLATE-D-"+uid)
        slug = graph["id"]+"-unit-"+uid.lower()
        root = dict(id=uid, kind="requirement", title=r["title"], referenceOnly=True,
                    projectionOf=dict(graphSlug=graph["id"], nodeId=uid))
        module = dict(id=d["id"], version=graph["sourceContentSHA256"],
                      goalRequirementId=uid, methodDecisionId=d["id"], childRequirementIds=[],
                      applicability=r["boundedResponsibility"],
                      successCriteria="Достаточно выполнить применимую Unit-specific Guidance и её checkpoints; инструкция не доказывает результат.")
        children.append(dict(schemaVersion=1,id=slug,title="Unit · "+r["title"],revision=1,
            planningScale="unit",identitySpace=graph["identitySpace"],rootRequirementId=uid,
            readOnly=True,templateOnly=True,selected=False,catalogHidden=True,
            preparedModule=module,sourceDocument=r["source"],
            sourceContentSHA256=graph["sourceContentSHA256"],
            sourceOwnerGraphSlug=graph["id"],sourceAnchor=r["sourceAnchor"],
            coverage="Готовый способ одного узкого R; без выдуманных под-R и без выбора проекта.",
            nodes=[root,d],edges=[dict(id="UNIT-E-DRIVE",type="DRIVES",**{"from":uid},to=d["id"],
                templateOnly=True,meaning="Готовый ответ на узкую задачу; пока не выбран.")],events=[]))
    graph["nodes"] = [n for n in graph["nodes"] if n["id"] not in {"TEMPLATE-D-"+uid for uid in unit_ids}]
    graph["edges"] = [e for e in graph["edges"] if e["type"] != "DRIVES" or e["from"] not in unit_ids]
    graph["conversionNote"] += " Unit-ответы раскрыты в отдельных графах, исходный R и полный источник принадлежат широкому модулю."
    return children

def write_projection(graph):
    dest=GRAPH_ROOT/graph["id"]/"graph.json"
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():
        old=json.loads(dest.read_text(encoding="utf-8"))
        ensure(old.get("templateOnly") is True, "Refusing to overwrite user graph "+str(dest))
        if old.get("preparedModule"):
            ensure(old["preparedModule"]["version"] == graph["preparedModule"]["version"],
                   "SOURCE_VERSION_CHANGED: preserve the old prepared version; create a separate versioned graph")
    dest.write_text(json.dumps(graph,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

def main():
    register=registry_entries(REGISTRY.read_text(encoding="utf-8"))
    sources=list(sorted((PROFILE/"target-modules").glob("TM-2D-*.md")))
    ensure(len(sources)==10 and len(register)==10,"Profile registry/source list not exactly 10")
    for file in sources:
        mid=file.stem
        ensure(mid in register,"Unregistered: "+mid)
        graph=construct(file,dict(register[mid],id=mid))
        children = unit_graphs(graph)
        write_projection(graph)
        for child in children:
            write_projection(child)
        print(f"BUILT {graph['id']} modules=1 units={graph['unitCount']} nodes={len(graph['nodes'])} edges={len(graph['edges'])} sourcebytes={len(file.read_bytes())}")
    print("ALL_2D_TEMPLATES_BUILT")

if __name__=="__main__":
    try:main()
    except (ValueError,OSError) as e:
        print("ERROR: "+str(e),file=sys.stderr)
        sys.exit(2)

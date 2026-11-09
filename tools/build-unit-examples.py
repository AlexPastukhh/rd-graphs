#!/usr/bin/env python3
"""One-R prepared examples: a broad module, direct/split Unit, recursive Units."""
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
SPACE = "example:module-unit-v1"
SOURCE = "docs/examples/MODULE-UNIT-GUIDE.md"
guide = (ROOT / SOURCE).read_text()
VERSION = hashlib.sha256(guide.encode()).hexdigest()
specs = [
    ("reference-module-units", "module", "UD-R-FEATURE", "Проработать функцию", "UD-D-FEATURE",
     "Описать результат и проработать состояние/переходы", ["UD-R-RESULT", "UD-R-STATE-PATH"]),
    ("reference-unit-direct", "unit", "UD-R-RESULT", "Описать наблюдаемый результат", "UD-D-RESULT",
     "Записать наблюдаемый результат и критерий его проверки", []),
    ("reference-unit-split", "unit", "UD-R-STATE-PATH", "Проработать состояние и переходы", "UD-D-STATE-PATH",
     "Отдельно определить состояния и переходы между ними", ["UD-R-STATES", "UD-R-TRANSITIONS"]),
    ("reference-unit-states", "unit", "UD-R-STATES", "Определить состояния", "UD-D-STATES",
     "Перечислить только различимые состояния", []),
    ("reference-unit-transitions", "unit", "UD-R-TRANSITIONS", "Определить переходы", "UD-D-TRANSITIONS",
     "Для каждого существенного перехода указать условие и результат", []),
]
titles = {r:title for _,_,r,title,_,_,_ in specs}
owners = {r:slug for slug,_,_,_,_,_,children in specs for r in children}
for slug,scale,r,title,d,answer,children in specs:
    root = dict(id=r,kind="requirement",title=title)
    if r in owners:
        root["projectionOf"] = {"graphSlug":owners[r],"nodeId":r}
        root["referenceOnly"] = True
    nodes = [root,dict(id=d,kind="decision",title=answer,status="reusable-unselected",selected=False)]
    edges = [dict(id=d+"-drive",type="DRIVES",**{"from":r},to=d,templateOnly=True,
                  meaning="Подготовленный способ ответа на R; реального выбора нет.")]
    for child in children:
        nodes.append(dict(id=child,kind="requirement",title=titles[child]))
        edges.append(dict(id=d+"-"+child,type="INTRODUCES",**{"from":d},to=child,parent=r,templateOnly=True,
                          meaning="Потенциальный под-R этого способа; не принятый план."))
    graph = dict(schemaVersion=1,id=slug,title=("Unit · " if scale=="unit" else "TM · ")+title,revision=1,
        planningScale=scale,identitySpace=SPACE,rootRequirementId=r,readOnly=True,templateOnly=True,
        catalogHidden=scale=="unit",sourceDocument=SOURCE,sourceContentSHA256=VERSION,
        preparedModule=dict(id=d,version=VERSION,goalRequirementId=r,methodDecisionId=d,
                            childRequirementIds=children,applicability=title,successCriteria=answer),
        nodes=nodes,edges=edges,events=[])
    if scale=="module":graph["sourceMarkdown"] = guide
    else:graph["sourceOwnerGraphSlug"] = "reference-module-units"
    path=ROOT/"graphs/examples"/slug/"graph.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        old=json.loads(path.read_text())
        assert old.get("templateOnly") is True and old["id"]==slug
    path.write_text(json.dumps(graph,ensure_ascii=False,indent=2)+"\n")
print("MODULE_UNIT_EXAMPLES",len(specs))

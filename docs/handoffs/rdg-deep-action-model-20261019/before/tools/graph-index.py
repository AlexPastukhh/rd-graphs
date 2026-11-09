#!/usr/bin/env python3
"""Refresh the graph catalog and locally bundled graph snapshot for Tampermonkey."""
import json
import os
import tempfile
from pathlib import Path
from importlib.machinery import SourceFileLoader
catalog_module = SourceFileLoader("rdg_catalog_library", str(Path(__file__).with_name("rdg-catalog.py"))).load_module()

ROOT = Path(__file__).resolve().parent.parent / "graphs"
INDEX = ROOT / "index.json"
BUNDLE = ROOT.parent / "tools" / "rd-graph-data.js"


def atomic_write(path, content):
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".graph-index-", suffix=".tmp", delete=False) as out:
            tmp = out.name
            os.fchmod(out.fileno(), 0o644)
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def build_catalog(overrides=None):
    """Validate a whole catalog in memory; overrides use group/slug/graph.json keys."""
    overrides = overrides or {}
    bundled, folders = catalog_module.discover(ROOT, overrides)
    state = SourceFileLoader("rdg_state_index", str(ROOT.parent / "tools/rdg-state.py")).load_module()
    state.validate_items(bundled)
    entries = []
    for item in bundled:
        graph = item['graph']
        if not isinstance(graph, dict) or graph.get('schemaVersion') != 1:
            raise ValueError(f"invalid graph schemaVersion: {item['file']}")
        if graph.get('planningScale', 'module') not in {'module', 'unit'}:
            raise ValueError(f"invalid planningScale: {item['slug']}")
        entries.append({**{k:v for k,v in item.items() if k != 'graph'},
                        "identitySpace":graph.get("identitySpace"),
                        "rootRequirementId":graph.get("rootRequirementId")})
    # Identity is attached to Requirements, not directly to graph files.
    # Two graphs are related only if:
    # (1) their explicit identitySpace is the same, (2) a concrete
    # INTRODUCES edge creates R in the producing graph, and (3) another
    # graph declares that very R as its rootRequirementId.
    # Names/title similarity or parentGraphSlug/nextGraphSlug do NOT create links.
    relations = []
    by_scope = {}
    by_slug = {item["slug"]: item for item in bundled}

    def resolve_record(item, node, trail=()):
        ref = node.get("projectionOf")
        if ref is None:
            return node
        if not isinstance(ref, dict):
            raise ValueError(f"invalid projectionOf: {item['slug']}:{node.get('id')}")
        key = (item["slug"], node.get("id"))
        if key in trail:
            raise ValueError(f"cyclic projectionOf: {key}")
        owner = by_slug.get(ref.get("graphSlug"))
        if (not owner or ref.get("nodeId") != node.get("id") or
                owner["graph"].get("identitySpace") != item["graph"].get("identitySpace")):
            raise ValueError(f"unresolved identity owner: {key}")
        matches = [n for n in owner["graph"]["nodes"] if n.get("id") == ref["nodeId"]]
        if len(matches) != 1 or matches[0].get("kind") != node.get("kind"):
            raise ValueError(f"incompatible identity owner: {key}")
        record = resolve_record(owner, matches[0], (*trail, key))
        # A projection may have a local display title/description, but not
        # silently replace the normative statement or scope of its owner.
        for field in ("requirementText", "scope"):
            if field in node and node[field] != record.get(field):
                raise ValueError(f"projection overrides {field}: {key}")
        return record

    # One semantic owner per (identitySpace, node ID), including non-root nodes.
    # Other appearances of the same record must declare projectionOf; the
    # existing resolver below verifies the reference and its scope.
    identity_owners = {}
    for item in bundled:
        space = item["graph"].get("identitySpace")
        if not isinstance(space, str) or not space.strip():
            continue
        for node in item["graph"]["nodes"]:
            if node.get("projectionOf") is not None:
                continue
            key = (space, node["id"])
            previous = identity_owners.get(key)
            if previous is not None:
                raise ValueError(f"duplicate identity owner: {key} in {previous} and {item['slug']}; use projectionOf")
            identity_owners[key] = item["slug"]

    # Validate explicit references even if they do not produce a child level.
    for item in bundled:
        for node in item["graph"]["nodes"]:
            if node.get("projectionOf") is not None:
                space = item["graph"].get("identitySpace")
                if not isinstance(space, str) or not space.strip():
                    raise ValueError(f"projection requires identitySpace: {item['slug']}:{node.get('id')}")
                resolve_record(item, node)

    # Prepared modules are typed whole plans, not accepted project decisions.
    for item in bundled:
        g = item["graph"]
        # Source checksum must match source bytes, not just the copied
        # sourceContentSHA256 field in a referencing Decision.
        source_text = g.get("sourceMarkdown")
        if source_text is not None:
            import hashlib
            if (not isinstance(source_text, str) or
                    g.get("sourceContentSHA256") != hashlib.sha256(source_text.encode("utf-8")).hexdigest()):
                raise ValueError(f"sourceContentSHA256 differs from sourceMarkdown: {item['slug']}")
        source_owner_slug = g.get("sourceOwnerGraphSlug")
        if source_owner_slug is not None:
            source_owner = by_slug.get(source_owner_slug)
            if (not source_owner or source_owner_slug == item["slug"] or
                    not isinstance(source_owner["graph"].get("sourceMarkdown"), str) or
                    source_owner["graph"].get("sourceContentSHA256") != g.get("sourceContentSHA256")):
                raise ValueError(f"unresolved source owner: {item['slug']}")
            if g.get("sourceAnchor") is not None and (
                not isinstance(g["sourceAnchor"], str) or
                g["sourceAnchor"] not in source_owner["graph"]["sourceMarkdown"]
            ):
                raise ValueError(f"unresolved source anchor: {item['slug']}")
        module = g.get("preparedModule")
        if module is not None:
            if not isinstance(module, dict) or not all(isinstance(module.get(k), str) and module[k].strip()
                    for k in ("id", "version", "goalRequirementId", "methodDecisionId", "applicability", "successCriteria")):
                raise ValueError(f"invalid preparedModule: {item['slug']}")
            ns = {n["id"]: n for n in g["nodes"]}
            if (g.get("templateOnly") is not True or module["goalRequirementId"] != g.get("rootRequirementId") or
                    ns.get(module["goalRequirementId"], {}).get("kind") != "requirement" or
                    ns.get(module["methodDecisionId"], {}).get("kind") != "decision" or
                    ns[module["methodDecisionId"]].get("status") != "reusable-unselected"):
                raise ValueError(f"invalid prepared module goal/method: {item['slug']}")
            if not any(e.get("type") == "DRIVES" and e.get("from") == module["goalRequirementId"] and e.get("to") == module["methodDecisionId"] for e in g["edges"]):
                raise ValueError(f"prepared goal does not drive method: {item['slug']}")
            children = module.get("childRequirementIds")
            if not isinstance(children, list) or len(set(children)) != len(children):
                raise ValueError(f"invalid prepared children: {item['slug']}")
            introduced = {e["to"] for e in g["edges"] if e.get("type") == "INTRODUCES" and
                          e.get("from") == module["methodDecisionId"] and e.get("parent") == module["goalRequirementId"]}
            if set(children) != introduced:
                raise ValueError(f"prepared module composition differs: {item['slug']}")
        for n in g["nodes"]:
            binding = n.get("preparedModelRef")
            if binding is None or (g.get("readOnly") is True and isinstance(binding, str)):
                continue  # historical teaching variants retain their old literal provenance
            if not isinstance(binding, dict):
                raise ValueError(f"preparedModelRef must be typed: {item['slug']}:{n['id']}")
            source = by_slug.get(binding.get("graphSlug"))
            model = source["graph"].get("preparedModule") if source else None
            if not model or any(binding.get(k) != model.get(k) for k in ("id", "version", "goalRequirementId", "methodDecisionId")):
                raise ValueError(f"unresolved prepared module/version: {item['slug']}:{n['id']}")
            if binding.get("sourceContentSHA256") != source["graph"].get("sourceContentSHA256"):
                raise ValueError(f"prepared source version differs: {item['slug']}:{n['id']}")
            target = binding.get("targetRequirementId")
            if n.get("kind") != "decision" or not any(e.get("type") == "DRIVES" and
                    e.get("from") == target and e.get("to") == n["id"] for e in g["edges"]):
                raise ValueError(f"prepared application driver missing: {item['slug']}:{n['id']}")
            mappings = binding.get("requirementBindings", {})
            if not isinstance(mappings, dict) or set(mappings) != set(model["childRequirementIds"]):
                raise ValueError(f"invalid prepared child bindings: {item['slug']}:{n['id']}")
            actual = {e["to"] for e in g["edges"] if e.get("type") == "INTRODUCES" and
                      e.get("from") == n["id"] and e.get("parent") == target}
            if any(not isinstance(v, list) or not v or any(r not in actual for r in v) for v in mappings.values()):
                raise ValueError(f"prepared child binding does not match introduction: {item['slug']}:{n['id']}")
            mapped = {r for values in mappings.values() for r in values}
            if mapped != actual:
                raise ValueError(f"prepared child bindings omit introduced Requirements: {item['slug']}:{n['id']}")

    def is_selected(graph, decision):
        if graph.get("templateOnly") or decision.get("templateOnly"):
            return False
        if decision.get("status") == "committed":
            return graph.get("exampleOnly") is not True
        return (decision.get("status") == "selected-in-example-only" and
                graph.get("exampleOnly") is True and graph.get("hypothetical") is True and
                graph.get("readOnly") is True and graph.get("selectedInProject") is False)
    for item in bundled:
        g = item["graph"]
        space, root_id = g.get("identitySpace"), g.get("rootRequirementId")
        if not isinstance(space, str) or not space.strip():
            continue
        if isinstance(root_id, str):
            root_nodes = [n for n in g["nodes"] if n.get("id") == root_id
                          and n.get("kind") == "requirement"]
            if len(root_nodes) != 1:
                raise ValueError(f"invalid rootRequirementId for {item['slug']}: {root_id}")
            key = (space, root_id)
            if key in by_scope:
                raise ValueError(f"duplicate root Requirement across files: {key}")
            by_scope[key] = item
    for item in bundled:
        g = item["graph"]
        space = g.get("identitySpace")
        if not isinstance(space, str) or not space.strip():
            continue
        requirements = {n["id"] for n in g["nodes"]
                        if n.get("kind") == "requirement"}
        decisions = {n["id"]: n for n in g["nodes"]
                     if n.get("kind") == "decision"}
        actions = {n["id"]: n for n in g["nodes"]
                   if g.get("actionModel") == "candidate-v6" and n.get("kind") == "action"}
        nodes = {n["id"]: n for n in g["nodes"]}
        drivers = {(e.get("from"), e.get("to")) for e in g["edges"]
                   if e.get("type") == "DRIVES"}
        for edge in g["edges"]:
            if edge.get("type") != "INTRODUCES":
                continue
            rid = edge.get("to")
            target = by_scope.get((space, rid))
            if not target or target["slug"] == item["slug"]:
                continue
            cause = decisions.get(edge.get("from")) or actions.get(edge.get("from"))
            if (rid not in requirements or cause is None or
                    edge.get("parent") not in requirements):
                raise ValueError(f"invalid introduction across files: {item['slug']}:{edge.get('id')}")
            is_action = cause["kind"] == "action"
            prepared = (not is_action and g.get("templateOnly") is True and
                        isinstance(g.get("preparedModule"), dict) and
                        edge["from"] == g["preparedModule"]["methodDecisionId"] and
                        rid in g["preparedModule"]["childRequirementIds"])
            authorized_action = (is_action and cause.get("status") == "selected" and
                                 g.get("templateOnly") is not True and g.get("exampleOnly") is not True and
                                 any(ev.get("type") == "action_selected" and
                                     ev.get("actionId") == cause["id"] and
                                     ev.get("driverRequirementId") == edge.get("parent") and
                                     ev.get("by") in ("user", "assistant") for ev in g.get("events", [])))
            if edge.get("candidate") or (not prepared and
                    (edge.get("templateOnly") or
                     not (authorized_action if is_action else is_selected(g, cause)))):
                continue
            if (edge.get("parent"), edge["from"]) not in drivers:
                raise ValueError(f"introduction parent does not drive Action/D: {item['slug']}:{edge.get('id')}")
            source_record = resolve_record(item, nodes[rid])
            target_node = next(n for n in target["graph"]["nodes"] if n["id"] == rid)
            target_record = resolve_record(target, target_node)
            source_text = source_record.get("requirementText", source_record.get("title", ""))
            target_text = target_record.get("requirementText", target_record.get("title", ""))
            if not all(isinstance(text, str) and text.strip() for text in (source_text, target_text)):
                raise ValueError(f"invalid Requirement statement: {space}:{rid}")
            if " ".join(source_text.split()) != " ".join(target_text.split()):
                raise ValueError(f"conflicting Requirement identity: {space}:{rid}; "
                                 "use an explicit projectionOf owner for local display text")
            if ("scope" in source_record and "scope" in target_record and
                    source_record["scope"] != target_record["scope"]):
                raise ValueError(f"conflicting Requirement scope: {space}:{rid}")
            # A record owner may keep historical/deeper records; navigation
            # starts at the declared one-level expansion of the driver R.
            producer = by_scope.get((space, edge.get("parent")), item)
            if (producer["graph"].get("view", {}).get("requirementDepth") != 1 or
                    not any(e == edge for e in producer["graph"]["edges"])):
                producer = item
            relations.append({
                "from": producer["slug"], "to": target["slug"],
                "requirementId": rid, "identitySpace": space,
                **({"introducedByActionId": edge["from"]} if is_action
                   else {"introducedByDecisionId": edge["from"]}),
                "introductionEdgeId": edge.get("id"),
                "relationKind": "prepared" if prepared else "selected",
                "fromGroup": item["group"], "toGroup": target["group"],
            })
    # A prospective inter-graph R is only a *plan* under the originating
    # option, not a selected/INTRODUCES child.  A separate graph may expand
    # that R only when both the owner and the exact option->R OUTCOME_OF edge
    # are present and the target declares its identity projection explicitly.
    for item in bundled:
        g=item["graph"]
        space=g.get("identitySpace")
        nodes={n["id"]:n for n in g["nodes"]}
        for edge in g["edges"]:
            if edge.get("type")!="OUTCOME_OF" or edge.get("archived") is True:
                continue
            rid, oid=edge.get("to"),edge.get("from")
            source_r, option=nodes.get(rid),nodes.get(oid)
            if not source_r or source_r.get("kind")!="requirement" or source_r.get("status") not in ("candidate","potential"):
                continue
            if not option or option.get("kind")!="option":
                continue
            target=by_scope.get((space,rid))
            if not target or target["slug"]==item["slug"]:
                continue
            target_graph=target["graph"]
            # A writable self-authored paper branch is just as legitimate as
            # a read-only teaching example, provided both sources belong to
            # the same writable project and an exact expansionOf/projectionOf
            # binding below proves continuity. Never import a read-only source
            # into an active project by merely matching an R title/ID.
            teaching = (g.get("readOnly") is True and g.get("exampleOnly") is True and
                        target_graph.get("readOnly") is True and target_graph.get("exampleOnly") is True)
            writable = (g.get("readOnly") is not True and g.get("exampleOnly") is not True and
                        target_graph.get("readOnly") is not True and target_graph.get("exampleOnly") is not True)
            if not (teaching or writable):
                continue
            expected={"graphSlug":item["slug"],"nodeId":rid}
            target_root=next((n for n in target_graph["nodes"] if n.get("id")==rid and n.get("kind")=="requirement"),None)
            # The owner graph may contain the same potential R and OUTCOME_OF
            # for an overview, while a deeper child file is its direct
            # expansion. Only that declared immediate expansion creates a
            # navigation edge; the earlier overview is not an extra parent.
            if target_graph.get("expansionOf")!=expected:
                continue
            if not target_root or target_root.get("projectionOf")!=expected:
                raise ValueError(f"prospective child must project its exact owner: {item['slug']}:{rid}")
            if resolve_record(item,source_r)!=resolve_record(target,target_root):
                raise ValueError(f"prospective Requirement identity mismatch: {item['slug']}:{rid}")
            parents=[e for e in g["edges"] if e.get("type")=="OPTION_FOR" and e.get("to")==oid]
            if len(parents)!=1:
                raise ValueError(f"prospective option has no unique driver R: {item['slug']}:{oid}")
            if any(r["to"]==target["slug"] and r["requirementId"]==rid for r in relations):
                raise ValueError(f"ambiguous prospective/selected target: {item['slug']}:{rid}")
            relations.append({
                "from":item["slug"],"to":target["slug"],"requirementId":rid,
                "identitySpace":space,"relationKind":"potential",
                "originatingOptionId":oid,"originatingRequirementId":parents[0]["from"],
                "outcomeEdgeId":edge.get("id"),
                "introducedByDecisionId":"",
                "fromGroup":item["group"],"toGroup":target["group"],
            })
    # Content refinements keep their own origin; they are never labelled a selected D.
    for item in bundled:
        g = item["graph"]
        for edge in g["edges"]:
            if edge.get("type") != "DERIVES" or edge.get("candidate") or edge.get("templateOnly") or edge.get("archived"):
                continue
            target = by_scope.get((g.get("identitySpace"), edge.get("to")))
            if not target or target["slug"] == item["slug"]:
                continue
            src = next((n for n in g["nodes"] if n["id"] == edge["to"] and n["kind"] == "requirement"), None)
            dst = next(n for n in target["graph"]["nodes"] if n["id"] == edge["to"])
            if src is None or resolve_record(item, src).get("title") != resolve_record(target, dst).get("title"):
                raise ValueError(f"conflicting derived identity: {item['slug']}:{edge['id']}")
            relations.append({"from": item["slug"], "to": target["slug"], "requirementId": edge["to"],
                              "identitySpace": g["identitySpace"], "introducedByDecisionId": "",
                              "derivationEdgeId": edge["id"], "relationKind": "derived",
                              "fromGroup": item["group"], "toGroup": target["group"]})

    # An explicit record expansion proves only the same R/owner, not its origin.
    for target in bundled:
        g = target["graph"]
        ref = g.get("expansionOf")
        if ref is None:
            continue
        source = by_slug.get(ref.get("graphSlug")) if isinstance(ref, dict) else None
        rid = g.get("rootRequirementId")
        if not source or ref.get("nodeId") != rid or source["graph"].get("identitySpace") != g.get("identitySpace"):
            raise ValueError(f"invalid expansionOf: {target['slug']}")
        src = next((n for n in source["graph"]["nodes"] if n["id"] == rid and n["kind"] == "requirement"), None)
        dst = next((n for n in g["nodes"] if n["id"] == rid), None)
        if not src or not dst or resolve_record(source, src) != resolve_record(target, dst):
            raise ValueError(f"expansion must reference the same owner: {target['slug']}")
        if not any(r["from"] == source["slug"] and r["to"] == target["slug"] and r["requirementId"] == rid for r in relations):
            relations.append({"from":source["slug"],"to":target["slug"],"requirementId":rid,
                "identitySpace":g["identitySpace"],"introducedByDecisionId":"",
                "relationKind":"same-requirement","fromGroup":source["group"],"toGroup":target["group"]})

    # Owner and projection can carry the exact same introduction, not two paths.
    relations = list({(r["from"], r["to"], r["requirementId"], r["relationKind"]): r
                      for r in relations}.values())
    # A cycle spread across different files is still a plan cycle.
    outgoing = {item["slug"]: [] for item in bundled}
    for r in relations:
        outgoing[r["from"]].append(r["to"])
    visiting, visited = set(), set()
    def visit_graph(slug):
        if slug in visiting:
            raise ValueError(f"cycle across graph levels: {slug}")
        if slug in visited:
            return
        visiting.add(slug)
        for target in outgoing[slug]:
            visit_graph(target)
        visiting.remove(slug)
        visited.add(slug)
    for slug in outgoing:
        visit_graph(slug)

    # Project context is a derived, identitySpace-scoped read model, not a
    # second authoritative copy. Prepared libraries and teaching examples
    # never enter the situation of a writable user project.
    project_contexts = {}
    for item in bundled:
        g=item["graph"]
        if item["group"] != "workspaces" or not g.get("identitySpace"):
            continue
        space=g["identitySpace"]
        ctx=project_contexts.setdefault(space, {"identitySpace":space, "graphSlugs":[], "records":[], "collections":[]})
        ctx["graphSlugs"].append(item["slug"])
        records=g.get("nodes",[])
        for n in records:
            if n.get("projectionOf") or n.get("active") is False or n.get("status") in ("inactive","superseded","rejected","candidate","potential"):
                continue
            if n.get("kind") not in ("requirement","decision","context"):
                continue
            if n.get("kind") == "decision" and n.get("status") != "committed":
                continue
            ctx["records"].append({"id":n["id"],"kind":n["kind"],"title":n["title"],
                                  "graphSlug":item["slug"],"status":n.get("status","active"),
                                  "currentStatement":n.get("currentStatement",n["title"]),
                                  # This is a project inventory, NOT a claim of
                                  # applicability in every R/scope/time.
                                  **{k:n[k] for k in ("scope","scopeCompatibility","effectiveAt","validFrom",
                                                     "validUntil","validTo","knownAt","recordedAt")
                                     if k in n}})
        for col in g.get("collections",[]):
            ctx["collections"].append({"id":col["id"],"title":col["title"],
                                       "graphSlug":item["slug"],"memberRefs":col["memberRefs"]})
    # Cross-file impact is a derived review hint, never a second graph owner.
    # A changed R may affect option canons/QRPE in another R-owned file.
    for ctx in project_contexts.values():
        space=ctx["identitySpace"]
        scoped=[item for item in bundled if item["group"]=="workspaces" and
                item["graph"].get("identitySpace")==space]
        changed={n["id"] for item in scoped for n in item["graph"]["nodes"]
                 if n.get("kind")=="requirement" and
                 (n.get("active") is False or n.get("status")=="inactive")}
        for item in scoped:
            changed.update(e.get("requirementId") for e in item["graph"].get("events",[])
                           if e.get("type")=="requirement_reparented")
            # T2/T3 of a composite can challenge the T1 selection basis.
            # We never infer that a prior decision was revised.
            for n in item["graph"]["nodes"]:
                if (n.get("kind")=="requirement" and n.get("compositeOf")
                        and len(n.get("history",[]))>1):
                    changed.add(n["id"])
                    changed.add(n["compositeOf"])
        collection_members={}
        for item in scoped:
            for col in item["graph"].get("collections",[]):
                collection_members[(item["slug"],col["id"])]=set(col["memberRefs"])
        alerts=[]
        for item in scoped:
            for n in item["graph"]["nodes"]:
                if n.get("projectionOf") or n.get("status") in ("inactive","superseded","rejected"):
                    continue
                refs=set()
                for q in n.get("qrpe",[]):
                    if q.get("ref"):refs.add(q["ref"])
                    refs.update(q.get("sourceRefs",[]))
                for entry in n.get("history",[]):
                    refs.update(f.get("ref") for f in entry.get("facts",[]) if isinstance(f,dict))
                selected=n.get("selectionBasis",{}).get("compositeSnapshot",{})
                if isinstance(selected,dict):
                    for entry in selected.get("history",[]):
                        refs.update(f.get("ref") for f in entry.get("facts",[]) if isinstance(f,dict))
                for part in (n, n.get("selectionBasis",{}).get("optionSnapshot",{})):
                    block=part.get("canonBlock",{}) if isinstance(part,dict) else {}
                    for key in ("recommended","contraindicated"):
                        for case in block.get(key,[]):
                            refs.update(case.get("checkRequirements",[]))
                            for collection_ref in case.get("checkCollections",[]):
                                # Strings are owner-local. Cross-graph Collections
                                # require an explicit qualified source reference.
                                if isinstance(collection_ref,str):
                                    owner_slug,collection_id=item["slug"],collection_ref
                                elif isinstance(collection_ref,dict):
                                    owner_slug=collection_ref.get("graphSlug")
                                    collection_id=collection_ref.get("collectionId")
                                else:
                                    continue
                                refs.update(collection_members.get((owner_slug,collection_id),set()))
                basis=n.get("selectionBasis",{})
                snap=basis.get("compositeSnapshot") if isinstance(basis,dict) else None
                if isinstance(snap,dict):
                    source=next((r for source_item in scoped for r in source_item["graph"]["nodes"]
                                 if r.get("id")==snap.get("id") and r.get("kind")=="requirement"
                                 and source_item["slug"]==item["slug"]),None)
                    if source and source.get("history",[])!=snap.get("history",[]):
                        refs.add(source.get("id"))
                impacted=sorted(x for x in refs & changed if x is not None and x!=n["id"])
                if impacted:
                    alerts.append({"graphSlug":item["slug"],"nodeId":n["id"],
                                   "sourceRequirementIds":impacted,"status":"needs-review"})
        ctx["reviewAlerts"]=alerts
        ctx["graphSlugs"].sort()
        ctx["records"].sort(key=lambda n:(n["graphSlug"],n["id"]))
        ctx["collections"].sort(key=lambda n:(n["graphSlug"],n["id"]))

    # A historical preparedSource pin remains immutable at T1. If the
    # currently available library has changed since that pin, report it as
    # a REVIEW hint, never as evidence that past selection used new data.
    # This is a derived index view; it does not authorize an upgrade.
    import hashlib
    source_update_alerts = []
    for item in bundled:
        for node in item["graph"]["nodes"]:
            pin = node.get("preparedSource")
            if not isinstance(pin, dict):
                continue
            slug = pin.get("graphSlug")
            source = by_slug.get(slug)
            source_node = next((x for x in source["graph"]["nodes"]
                                if x.get("id") == pin.get("sourceOptionId") and
                                x.get("kind") == "option"), None) if source else None
            if not source_node:
                reason = "source-option-unavailable"
                available_revision = None
            else:
                sg = source["graph"]
                available_revision = str(sg.get("sourceVersion", sg.get("version", sg.get("revision"))))
                canon_digest = hashlib.sha256(json.dumps(
                    source_node.get("canonBlock"), ensure_ascii=False, sort_keys=True,
                    separators=(",", ":")).encode("utf-8")).hexdigest()
                if pin.get("version") != available_revision:
                    reason = "available-version-differs-from-pin"
                elif pin.get("canonHash") != canon_digest:
                    reason = "available-canon-differs-from-pin"
                else:
                    continue
            source_update_alerts.append({
                "graphSlug": item["slug"], "nodeId": node["id"],
                "sourceGraphSlug": slug, "sourceOptionId": pin.get("sourceOptionId"),
                "pinnedVersion": pin.get("version"),
                "availableVersion": available_revision, "reason": reason,
                "status": "needs-assessment-not-auto-upgrade"
            })
    source_update_alerts.sort(key=lambda a: (a["graphSlug"], a["nodeId"]))
    relations.sort(key=lambda r: (r["from"], r["requirementId"], r["to"]))
    default = "try-it" if any(e["slug"] == "try-it" for e in entries) else (
        entries[0]["slug"] if entries else None)
    layouts_path = ROOT / "layouts.json"
    layouts = json.loads(layouts_path.read_text()) if layouts_path.exists() else {"schemaVersion": 1, "revision": 0, "layouts": {}}
    if (layouts.get("schemaVersion") != 1 or not isinstance(layouts.get("revision"), int)
            or layouts["revision"] < 0 or not isinstance(layouts.get("layouts"), dict)):
        raise ValueError("invalid layouts.json")
    # Entry points are source graphs whose root R is not an expansion,
    # refinement or alternate representation from another graph. This does
    # NOT use folder membership as a causality boundary.
    incoming = {r["to"] for r in relations if r.get("relationKind") in
                {"selected", "prepared", "potential", "derived", "same-requirement"}}
    full_graphs = []
    for item in entries:
        g = by_slug[item["slug"]]["graph"]
        rid = g.get("rootRequirementId")
        if (item["slug"] not in incoming and rid and
                any(n.get("kind") == "requirement" and n.get("id") == rid for n in g["nodes"])):
            full_graphs.append({"kind":"full-graph", "slug":item["slug"],
                                "rootRequirementId":rid, "identitySpace":g["identitySpace"],
                                "folder":item["folder"], "title":item["title"],
                                "presentation":item.get("presentation",{}),"file":item["file"]})
    manifest = {"stateGraphs":[i for i in bundled if state.has_state(i["graph"]) or any(n.get("kind")=="context" for n in i["graph"]["nodes"])], "layouts": layouts, "schemaVersion": 1, "defaultGraph": default, "folders": folders, "fullGraphs": full_graphs, "graphs": entries, "relations": relations, "projectContexts": project_contexts, "sourceUpdateAlerts": source_update_alerts}
    payload = {"layouts": layouts, "schemaVersion": 1, "defaultGraph": default, "folders": folders, "fullGraphs": full_graphs, "graphs": [{**i, "identitySpace": i["graph"].get("identitySpace"), "rootRequirementId": i["graph"].get("rootRequirementId")} for i in bundled], "relations": relations, "projectContexts": project_contexts, "sourceUpdateAlerts": source_update_alerts}
    return manifest, payload


def rebuild_index():
    manifest, payload = build_catalog()
    atomic_write(INDEX, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    script = (
        "// Generated from catalog sources within local graphs/; do not edit manually.\n"
        "// Loaded by the RDG Tampermonkey loader via local @require.\n"
        "globalThis.RDG_EMBEDDED_GRAPHS = "
        + json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + ";\n"
    )
    atomic_write(BUNDLE, script)
    return len(manifest["graphs"])


if __name__ == "__main__":
    print(f"INDEX_UPDATED graphs={rebuild_index()}")

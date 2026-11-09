"""Validated RDG v7 planning records, kept compatible with schemaVersion 1.

This module manages semantic records, not a conversation transcript. The writer
supplies genuine selection authority; importing prepared text never grants it.
"""
import copy
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from importlib.machinery import SourceFileLoader
STATE = SourceFileLoader("rdg_state_bridge", str(ROOT / "tools/rdg-state.py")).load_module()

OPTION_ORIGINS = {"prepared", "situational", "adapted"}
ISSUE_STATUSES = {"open", "resolved", "accepted-risk", "invalidated", "superseded"}
CHILD_ROLES = {"subgoal", "method_correctness"}
KNOWN_STATES = {"checked-present", "checked-absent", "unknown", "unavailable", "stale"}
OPTIONS = {"candidate", "rejected", "historical"}
COLLECTION_PREFIX = "collection:"


def ensure(value, message):
    if not value:
        raise ValueError(message)


def finding_valid(issue):
    """Optional typed metadata on the existing QRPE owner, not another registry.

    F-P is a *confirmed* current problem. This first pilot cannot establish
    independent reality verification, so it must not mint F-P.
    """
    kind = issue.get("findingType")
    allowed = {"id", "text", "status", "findingType", "findingScope",
               "questions", "evidenceRefs", "proposalRefs", "alternatives",
               "temporalContext", "recordedAt", "effectiveAt",
               "statusHistory", "resolutionEvidenceRefs"}
    ensure(set(issue) <= allowed, "unsupported typed Finding field")
    ensure(kind in {"F-R", "F-U", "F-O", "F-P"}, "unknown Finding type")
    ensure(kind != "F-P", "F-P requires independently verified present evidence; "
           "unsupported by this pilot")
    ensure(issue.get("findingScope") in {"CURRENT", "UPSTREAM"},
           "Finding needs CURRENT or UPSTREAM scope")
    ensure(issue.get("status") == "open" or isinstance(issue.get("statusHistory"), list),
           "Finding needs explicit QRPE history")
    for key in ("questions", "evidenceRefs", "proposalRefs"):
        value = issue.get(key)
        ensure(isinstance(value, list) and
               all(isinstance(x, str) and bool(x.strip()) for x in value) and
               len(value) == len(set(value)), "invalid Finding " + key)
    if kind == "F-U":
        alternatives = issue.get("alternatives")
        ensure(isinstance(alternatives, list) and len(alternatives) >= 2 and
               all(isinstance(x, str) and bool(x.strip()) for x in alternatives) and
               len(set(alternatives)) == len(alternatives),
               "F-U requires at least two distinguishable alternatives")
    else:
        ensure("alternatives" not in issue, "alternatives belong to F-U")
    ensure("confirmed" not in issue and "selected" not in issue and
           "preselected" not in issue and "executionStatus" not in issue,
           "Finding cannot assert acceptance or execution")
    if "temporalContext" in issue:
        ctx = issue["temporalContext"]
        ensure(isinstance(ctx, dict) and set(ctx) ==
               {"planId", "planRevision", "stepId", "branchId", "outcome",
                "dependencyDigest", "status"} and
               ctx["status"] == "candidate" and
               isinstance(ctx["planId"], str) and bool(ctx["planId"]) and
               type(ctx["planRevision"]) is int and ctx["planRevision"] >= 1 and
               isinstance(ctx["stepId"], str) and bool(ctx["stepId"]) and
               isinstance(ctx["dependencyDigest"], str) and
               re.fullmatch(r"[0-9a-f]{64}", ctx["dependencyDigest"]) and
               (ctx["branchId"] is None or isinstance(ctx["branchId"], str)) and
               (ctx["outcome"] is None or isinstance(ctx["outcome"], str)),
               "invalid temporal Plan review provenance")


def issue_valid(issue):
    ensure(isinstance(issue, dict) and isinstance(issue.get("id"), str) and issue["id"], "QRPE requires id")
    ensure(isinstance(issue.get("text"), str) and issue["text"].strip(), "QRPE requires text")
    ensure(issue.get("status") in ISSUE_STATUSES, "invalid QRPE status")
    if "findingType" in issue:
        finding_valid(issue)
    else:
        ensure(not ({"findingScope", "questions", "proposalRefs",
                     "temporalContext", "alternatives"} & set(issue)),
               "typed Finding fields require findingType")
    if "recordedAt" in issue:
        ensure(isinstance(issue["recordedAt"], str) and issue["recordedAt"], "QRPE recordedAt must be string")
    if "effectiveAt" in issue:
        ensure(isinstance(issue["effectiveAt"], str) and issue["effectiveAt"], "QRPE effectiveAt must be string")
    transitions = issue.get("statusHistory", [])
    ensure(isinstance(transitions, list), "QRPE statusHistory must be array")
    seen = set()
    for item in transitions:
        ensure(isinstance(item, dict) and isinstance(item.get("id"), str)
               and item["id"] not in seen and item.get("status") in ISSUE_STATUSES
               and isinstance(item.get("recordedAt"), str) and item["recordedAt"],
               "invalid QRPE history entry")
        seen.add(item["id"])
    if transitions:
        ensure(issue["status"] == transitions[-1]["status"], "QRPE status/history mismatch")


def verify_prepared_source(option):
    """Fail closed: never claim a library pin that was not checked at selection."""
    pin = option.get("preparedSource")
    ensure(isinstance(pin, dict), "prepared source pin required")
    slug = pin.get("graphSlug")
    source_id = pin.get("sourceOptionId")
    ensure(isinstance(slug, str) and re.fullmatch(r"[a-z0-9][a-z0-9_-]*", slug)
           and isinstance(source_id, str) and source_id,
           "prepared source needs graphSlug and sourceOptionId")
    available = [ROOT / "graphs" / group / slug / "graph.json" for group in ("examples", "2d")]
    matches = [p for p in available if p.is_file() and not p.is_symlink()]
    ensure(len(matches) == 1, "PREPARED_SOURCE_MISSING_OR_AMBIGUOUS")
    source = json.loads(matches[0].read_text(encoding="utf-8"))
    ensure(source.get("readOnly") is True and source.get("templateOnly") is True,
           "prepared source must be read-only template")
    actual_version = str(source.get("sourceVersion", source.get("version", source.get("revision"))))
    ensure(pin.get("version") == actual_version, "PREPARED_SOURCE_VERSION_MISMATCH")
    source_option = next((n for n in source.get("nodes", []) if n.get("id") == source_id
                          and n.get("kind") == "option"), None)
    ensure(source_option and source_option.get("origin") == "prepared", "PREPARED_OPTION_MISSING")
    canon = source_option.get("canonBlock")
    digest = hashlib.sha256(json.dumps(canon, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()
    ensure(pin.get("canonHash") == digest, "PREPARED_CANON_HASH_MISMATCH")
    ensure(canon == option.get("canonBlock"), "PREPARED_CANON_CONTENT_MISMATCH: adapted needs own origin")
    return True


def validate_v7(g):
    """Validate optional v7 fields without rejecting historical read-only files."""
    STATE.validate_items([{"slug":g.get("id","local"), "group":"examples" if g.get("readOnly") else "workspaces", "graph":g}], partial=True)
    nodes = {n["id"]: n for n in g["nodes"]}
    for n in g["nodes"]:
        qrpe = n.get("qrpe", [])
        ensure(isinstance(qrpe, list), "qrpe must be list: " + n["id"])
        ids = set()
        for issue in qrpe:
            issue_valid(issue)
            ensure(issue["id"] not in ids, "duplicate QRPE id")
            ids.add(issue["id"])
        if n["kind"] == "option":
            ensure(n.get("origin") in OPTION_ORIGINS, "option origin required")
            ensure(n.get("status", "candidate") in OPTIONS, "candidate option cannot be committed D")
            block = n.get("canonBlock")
            ensure(isinstance(block, dict), "one canonBlock per option required")
            cases = set()
            for key in ("recommended", "contraindicated"):
                entries = block.get(key)
                ensure(isinstance(entries, list), "canonBlock requires "+key+" list")
                for case in entries:
                    ensure(isinstance(case, dict) and isinstance(case.get("id"), str) and case["id"], "canon case id required")
                    ensure(case["id"] not in cases, "duplicate canon case id")
                    cases.add(case["id"])
                    ensure(isinstance(case.get("text"), str) and case["text"].strip(), "canon case text required")
                    for field in ("checkCategories", "checkRequirements"):
                        if field in case:
                            ensure(isinstance(case[field], list) and all(isinstance(s,str) for s in case[field]), "invalid canon "+field)
                    # Bare Collection IDs are local to this option's owning graph.
                    # Cross-file lookup needs a qualified owner, never global ID union.
                    if "checkCollections" in case:
                        ensure(isinstance(case["checkCollections"], list), "invalid canon checkCollections")
                        for ref in case["checkCollections"]:
                            ensure((isinstance(ref, str) and bool(ref)) or
                                   (isinstance(ref, dict) and set(ref)=={"graphSlug","collectionId"} and
                                    all(isinstance(ref[k],str) and ref[k] for k in ("graphSlug","collectionId")) and
                                    re.fullmatch(r"[a-z0-9][a-z0-9_-]*",ref["graphSlug"])),
                                   "checkCollections requires local ID or graphSlug+collectionId")
            if n["origin"] == "prepared" and n.get("preparedSource") is not None:
                ref=n["preparedSource"]
                ensure(isinstance(ref, dict) and all(isinstance(ref.get(k), str) and ref[k] for k in ("graphSlug", "version", "canonHash")), "invalid prepared source pin")
        if n["kind"] == "requirement" and "compositeOf" in n:
            base = nodes.get(n["compositeOf"])
            ensure(base and base["kind"] == "requirement" and base["id"] != n["id"], "compositeOf must refer to another local R")
            ensure(isinstance(n.get("history"), list) and n["history"], "composite requires nonempty history")
            seen = set()
            for entry in n["history"]:
                ensure(isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry["id"] not in seen, "invalid composite revision")
                seen.add(entry["id"])
                ensure(isinstance(entry.get("recordedAt"), str) and entry["recordedAt"], "composite revision recordedAt required")
                ensure(isinstance(entry.get("statement"), str) and entry["statement"].strip(), "composite revision statement required")
                for fact in entry.get("facts", []):
                    ensure(isinstance(fact, dict) and fact.get("state") in KNOWN_STATES, "invalid context check state")
        if n["kind"] == "decision" and n.get("selectedOptionId") is not None:
            ensure(nodes.get(n["selectedOptionId"], {}).get("kind") == "option", "selectedOptionId not an option")
            ensure(isinstance(n.get("selectionBasis"), dict) and n["selectionBasis"].get("compositeSnapshot"), "chosen option needs immutable basis")
    for e in g["edges"]:
        if e["type"] == "OPTION_FOR":
            ensure(nodes[e["from"]]["kind"] == "requirement" and nodes[e["to"]]["kind"] == "option", "OPTION_FOR types")
        if e["type"] == "OUTCOME_OF":
            ensure(nodes[e["from"]]["kind"] == "option" and nodes[e["to"]]["kind"] == "requirement", "OUTCOME_OF types")
            if e.get("archived") is not True:
                ensure(nodes[e["to"]].get("status") in ("candidate", "potential"), "OUTCOME_OF may not imply actual R")
        if e["type"] == "INTRODUCES" and "childRole" in e:
            ensure(e["childRole"] in CHILD_ROLES, "invalid introduced R role")
    for col in g.get("collections", []):
        ensure(isinstance(col, dict) and isinstance(col.get("id"), str) and col["id"], "invalid collection")
        ensure(isinstance(col.get("title"), str) and col["title"].strip(), "collection title required")
        ensure(col.get("anchor") in nodes, "collection anchor missing")
        ensure(isinstance(col.get("memberRefs"), list) and col["memberRefs"], "collection memberRefs required")
        ensure(len(set(col["memberRefs"])) == len(col["memberRefs"]), "duplicate collection member")
        ensure(all(i in nodes for i in col["memberRefs"]), "collection member missing")
        # Collections group the *same* R-graph; no source or semantic owner transfer.
        ensure("rootRequirementId" not in col and "identitySpace" not in col and "ownerGraphSlug" not in col,
               "collection cannot be another semantic owner")
        ensure(col["anchor"] not in col["memberRefs"], "collection cannot contain anchor")
    ids = [x.get("id") for x in g.get("collections", [])]
    ensure(len(ids) == len(set(ids)), "duplicate collection")
    # The choice event is the only authority for an accepted D; options remain non-selected.
    for n in g["nodes"]:
        if n["kind"] != "decision" or n.get("status") != "committed" or not n.get("selectedOptionId"):
            continue
        selected = {e.get("decisionId") for e in g["events"] if e.get("type") in ("decision_selected", "decision_revised")}
        ensure(n["id"] in selected, "selected D must have event")
    return g


def apply_v7_operation(g, operation):
    """Return true when handled. Called within graph-apply.apply's revision-checked transaction."""
    name = operation.get("op")
    if name == "set_context_contract":
        # Definitions/usages are graph metadata, never a second owner of answers.
        contract = copy.deepcopy(operation.get("contract"))
        allowed = {"contextFields","contextUses","knowledgeSources","contextFieldsComplete"}
        ensure(isinstance(contract,dict) and set(contract)<=allowed, "invalid context contract")
        g.update(contract)
        return True
    if name in {"set_context_uses","set_canon_material"}:
        n=next((x for x in g["nodes"] if x["id"]==operation.get("targetId")),None)
        ensure(n and n["kind"] in {"requirement","option","context"} and not n.get("projectionOf"),
               "annotation needs owning R/option/Context")
        ensure(isinstance(operation.get("note"),str) and operation["note"].strip(),"annotation needs note")
        if name=="set_canon_material":
            ensure(n["kind"]=="option","canon material needs option")
            part=n["canonBlock"]
            changes=copy.deepcopy(operation.get("material"))
            ensure(isinstance(changes,dict) and set(changes)<={"sourceRefs","preparation","interpretation","fieldsComplete"},"invalid canon material")
        else:
            part=n
            if operation.get("caseId"):
                part=next((c for k in ("recommended","contraindicated") for c in n.get("canonBlock",{}).get(k,[]) if c["id"]==operation["caseId"]),None)
                ensure(part is not None,"canon case missing")
            changes={"contextUses":copy.deepcopy(operation.get("uses"))}
        n.setdefault("contextAnnotationHistory",[]).append({"note":operation["note"],"previous":{k:copy.deepcopy(part.get(k)) for k in changes}})
        part.update(changes)
        if n["kind"]=="option" and n.get("origin")=="prepared":
            n["origin"]="adapted"
        return True
    if name == "set_context_value":
        cid = operation.get("contextId")
        ref = copy.deepcopy(operation.get("fieldRef"))
        ensure("value" in operation,"set_context_value requires an explicit value or null")
        value = copy.deepcopy(operation["value"])
        ensure(isinstance(cid,str) and cid and isinstance(ref,dict) and
               (value is None or isinstance(value,dict)),"contextId/fieldRef/value required")
        n = next((x for x in g["nodes"] if x["id"]==cid),None)
        created=n is None
        if n is None:
            n = {"id":cid,"kind":"context","title":operation.get("title",cid)}
            g["nodes"].append(n)
        ensure(n.get("kind")=="context" and not n.get("projectionOf") and n.get("active") is not False
               and n.get("status") not in ("inactive","superseded"),"owning active Context required")
        ensure("contextFieldRef" not in n or n["contextFieldRef"]==ref,"cannot change field meaning of Context")
        if "contextFieldRef" not in n and not created:
            ensure(isinstance(operation.get("mappingNote"),str) and operation["mappingNote"].strip(),
                   "mapping existing freeform Context needs mappingNote")
            n["contextMapping"]={"note":operation["mappingNote"],
                                 "originalText":n.get("currentStatement",n.get("description",n["title"]))}
        n["contextFieldRef"]=ref
        if value is None:
            n.pop("contextValue",None)  # Empty field; do not create an answer history.
        else:
            n["contextValue"]=value
        return True
    if name == "add_option":
        n = copy.deepcopy(operation.get("option"))
        req = operation.get("requirementId")
        ensure(isinstance(n, dict) and n.get("kind") == "option", "add_option requires option node")
        ensure(any(x["id"] == req and x["kind"] == "requirement" for x in g["nodes"]), "unknown requirement for option")
        ensure(all(x["id"] != n["id"] for x in g["nodes"]), "option id exists")
        g["nodes"].append(n)
        g["edges"].append({"id": "option-for-"+n["id"], "type": "OPTION_FOR", "from": req, "to": n["id"]})
        return True
    if name == "add_collection":
        col = copy.deepcopy(operation.get("collection"))
        ensure(isinstance(col, dict) and col.get("id"), "missing collection")
        g.setdefault("collections", []).append(col)
        return True
    if name == "append_finding":
        # Finding is stored as a typed QRPE in the same semantic owner.
        target = next((n for n in g["nodes"] if n["id"] == operation.get("targetId")), None)
        ensure(target is not None and (target["kind"] in
               {"requirement", "decision", "option"} or
               (g.get("actionModel") == "candidate-v6" and target["kind"] == "action")),
               "Finding target missing")
        item = copy.deepcopy(operation.get("finding"))
        ensure(isinstance(item, dict) and item.get("status") == "open" and
               "findingType" in item and "statusHistory" not in item,
               "new Finding must be typed and start open")
        issue_valid(item)
        target.setdefault("qrpe", []).append(item)
        return True
    if name == "append_qrpe":
        target = next((n for n in g["nodes"] if n["id"] == operation.get("targetId")), None)
        ensure(target is not None and (target["kind"] in {"requirement", "decision", "option"} or
               (g.get("actionModel") == "candidate-v6" and target["kind"] == "action")), "QRPE target missing")
        entry = copy.deepcopy(operation.get("issue"))
        ensure(isinstance(entry, dict) and "findingType" not in entry,
               "typed Finding needs append_finding operation and grant")
        issue_valid(entry)
        target.setdefault("qrpe", []).append(entry)
        return True
    if name == "transition_qrpe":
        target = next((n for n in g["nodes"] if n["id"] == operation.get("targetId")), None)
        ensure(target and (target["kind"] in {"requirement", "decision", "option"} or
               (g.get("actionModel") == "candidate-v6" and target["kind"] == "action")), "QRPE target missing")
        issue = next((x for x in target.get("qrpe", []) if x["id"] == operation.get("issueId")), None)
        transition = copy.deepcopy(operation.get("transition"))
        ensure(issue is not None and isinstance(transition, dict), "QRPE transition needs existing issue")
        ensure(isinstance(transition.get("id"), str) and transition["id"] and
               isinstance(transition.get("recordedAt"), str) and transition["recordedAt"] and
               transition.get("status") in ISSUE_STATUSES and
               isinstance(transition.get("note"), str) and transition["note"].strip(),
               "QRPE transition needs ID, time, status and reason")
        ensure(issue["status"] != transition["status"], "QRPE status must change")
        history = issue.setdefault("statusHistory", [{"id": "initial", "status": issue["status"],
                                                      "recordedAt": issue.get("recordedAt", "unspecified")}])
        ensure(transition["id"] not in {h["id"] for h in history}, "duplicate QRPE transition")
        history.append(transition)
        issue["status"] = transition["status"]
        return True
    if name == "add_composite":
        n = copy.deepcopy(operation.get("requirement"))
        ensure(isinstance(n, dict) and n.get("kind") == "requirement" and n.get("compositeOf"), "composite must be R")
        ensure(n["id"] not in {x["id"] for x in g["nodes"]}, "composite id exists")
        g["nodes"].append(n)
        g["edges"].append({"id": "derived-composite-"+n["id"], "type": "DERIVES", "from": n["compositeOf"], "to": n["id"], "candidate": True})
        return True
    if name == "append_composite_revision":
        n=next((x for x in g["nodes"] if x["id"]==operation.get("requirementId") and x["kind"]=="requirement" and x.get("compositeOf")), None)
        ensure(n is not None, "composite R missing")
        rev=copy.deepcopy(operation.get("revision"))
        ensure(isinstance(rev, dict), "revision must be object")
        ensure(rev.get("id") not in {x.get("id") for x in n["history"]}, "duplicate composite revision")
        n["history"].append(rev)
        # The R statement evolves in history; rewriting its identity-owner title
        # would invalidate root projections in already-created child graphs.
        n["currentStatement"]=rev.get("statement", n.get("currentStatement",n["title"]))
        return True
    if name in {"deactivate_requirement", "reparent_requirement"}:
        rid=operation.get("requirementId")
        req=next((n for n in g["nodes"] if n["id"]==rid and n["kind"]=="requirement"),None)
        event=copy.deepcopy(operation.get("event"))
        event_type="requirement_deactivated" if name=="deactivate_requirement" else "requirement_reparented"
        ensure(req and not req.get("compositeOf") and req.get("active") is not False and
               req.get("status") not in ("candidate","potential","inactive","superseded"),
               "actual active non-composite Requirement required")
        ensure(isinstance(event,dict) and event.get("id") and event.get("type")==event_type and
               event.get("requirementId")==rid and event.get("by") in {"user","assistant"} and
               isinstance(event.get("note"),str) and event["note"].strip(),
               "material requirement change needs writer actor and note")
        ensure(event["id"] not in {x["id"] for x in g["events"]},"duplicate requirement event")
        if name=="deactivate_requirement":
            ensure(rid!=g.get("rootRequirementId"), "cannot deactivate root R without project-level revision")
            event["previousRequirementSnapshot"]=copy.deepcopy(req)
            req["status"]="inactive"
            req["active"]=False
            # Retain all edges in the historical file; they stop contributing to
            # the live planning graph. No D gets automatically superseded.
            for edge in g["edges"]:
                if edge.get("from")==rid or edge.get("to")==rid:
                    edge["archived"]=True
        else:
            old_edges=[e for e in g["edges"] if e["type"]=="INTRODUCES" and
                       e.get("to")==rid and not e.get("archived")]
            new_decision=next((n for n in g["nodes"] if n["id"]==operation.get("newDecisionId") and
                n["kind"]=="decision" and n.get("status")=="committed"),None)
            parent=operation.get("newParentId")
            ensure(new_decision and any(n["id"]==parent and n["kind"]=="requirement" for n in g["nodes"]),
                   "reparent requires committed D and actual parent R")
            ensure(any(e["type"]=="DRIVES" and e["from"]==parent and e["to"]==new_decision["id"]
                       and not e.get("archived") for e in g["edges"]),
                   "reparent parent must actually drive new D")
            ensure(old_edges,"reparent requires an existing active introduction")
            event["previousEdges"]=copy.deepcopy(old_edges)
            for edge in old_edges:edge["archived"]=True
            g["edges"].append({"id":"reparent-"+event["id"],"type":"INTRODUCES",
              "from":new_decision["id"],"to":rid,"parent":parent,
              "childRole":operation.get("childRole","subgoal")})
        g["events"].append(event)
        # Current basis may now be stale; flag a specific review, but preserve
        # the immutable T1 snapshot and all accepted Decisions.
        affected_collections={col["id"] for col in g.get("collections",[]) if rid in col.get("memberRefs",[])}
        for n in g["nodes"]:
            if n["id"]==rid:continue
            history=n.get("history",[])
            refs={fact.get("ref") for entry in history for fact in entry.get("facts",[])
                  if isinstance(fact,dict)}
            selected=n.get("selectionBasis",{}).get("compositeSnapshot",{})
            for entry in selected.get("history",[]) if isinstance(selected,dict) else []:
                refs.update(fact.get("ref") for fact in entry.get("facts",[]) if isinstance(fact,dict))
            refs.update(q.get("ref") for q in n.get("qrpe", []) if isinstance(q,dict))
            for q in n.get("qrpe", []):
                if isinstance(q.get("sourceRefs", []), list):
                    refs.update(q.get("sourceRefs", []))
            for container in (n, n.get("selectionBasis",{}).get("optionSnapshot",{})):
                if not isinstance(container,dict):continue
                block=container.get("canonBlock",{})
                for polarity in ("recommended","contraindicated"):
                    for case in block.get(polarity,[]) if isinstance(block,dict) else []:
                        refs.update(case.get("checkRequirements",[]))
                        if affected_collections.intersection(
                                ref for ref in case.get("checkCollections",[]) if isinstance(ref,str)):
                            refs.add(rid)
            if rid in refs:
                n["needsReview"]=True
                n.setdefault("impactSources",[])
                if event["id"] not in n["impactSources"]:n["impactSources"].append(event["id"])
        return True
    if name == "select_option":
        # Committed D is an intentional writer event, not an inference from source text.
        o=next((x for x in g["nodes"] if x["id"]==operation.get("optionId") and x["kind"]=="option"),None)
        driver=next((x for x in g["nodes"] if x["id"]==operation.get("driverId") and x["kind"]=="requirement"),None)
        decision=copy.deepcopy(operation.get("decision"))
        event=copy.deepcopy(operation.get("event"))
        ensure(o and driver, "selection needs real option and R driver")
        ensure(isinstance(decision,dict) and decision.get("kind")=="decision" and decision.get("status")=="committed", "selected D must be committed")
        ensure(isinstance(event,dict) and event.get("type")=="decision_selected" and event.get("by") in {"user","assistant"} and isinstance(event.get("note"),str) and event["note"].strip() and event.get("decisionId")==decision.get("id"), "selection needs a truthful user/assistant actor and material event")
        ensure(decision["id"] not in {n["id"] for n in g["nodes"]}, "decision id exists")
        edges=[e for e in g["edges"] if e["type"]=="OPTION_FOR" and e["to"]==o["id"]]
        ensure(len(edges)==1, "option must belong to exactly one R")
        base=edges[0]["from"]
        ensure(driver["id"]==base or driver.get("compositeOf")==base, "selected D must answer original or its composite")
        base_r=next(n for n in g["nodes"] if n["id"]==base)
        ensure(base_r.get("active") is not False and base_r.get("status") not in ("inactive","superseded"),
               "cannot select option for inactive original Requirement")
        ensure(driver.get("active") is not False and driver.get("status") not in ("inactive","superseded"),
               "cannot select option for inactive composite/driver")
        ensure(o.get("status","candidate")=="candidate", "only current candidate can be chosen")
        if o["origin"]=="prepared":
            verify_prepared_source(o)
        # A second choice for the same original R is only valid in a separate
        # explicit scope. Incompatible same-scope alternatives cannot both be actual.
        scope=decision.get("scope","default")
        ensure(isinstance(scope,str) and scope.strip(), "selected scope must be named")
        for existing in g["nodes"]:
            if existing["kind"]!="decision" or existing.get("status")!="committed":
                continue
            ref=existing.get("selectedOptionId")
            if ref and any(e["type"]=="OPTION_FOR" and e["to"]==ref and e["from"]==base for e in g["edges"]):
                old_scope=existing.get("scope","default")
                ensure(old_scope!=scope, "CONFLICTING_SELECTED_OPTIONS: same scope requires revision")
                # A declared disjoint pair cannot override an obvious
                # hierarchical overlap in explicit slash-delimited paths.
                a,b=old_scope.strip("/"),scope.strip("/")
                ensure(not (a.startswith(b+"/") or b.startswith(a+"/")),
                       "SCOPE_OVERLAP: nested scope paths cannot be declared disjoint")
                # Distinct strings alone are not evidence of disjoint scopes.
                ensure(old_scope in decision.get("disjointFromScopes", []) and
                       isinstance(decision.get("scopeDisjointReason"),str) and decision["scopeDisjointReason"].strip(),
                       "SCOPE_OVERLAP_UNKNOWN: explicit disjointness evidence required")
                # A free-text reason is provenance, not verified geometry.
                decision["scopeCompatibility"]="declared-unverified"
        qrpe=copy.deepcopy(o.get("qrpe",[]))
        decision["selectedOptionId"]=o["id"]
        decision["qrpe"]=qrpe
        decision["selectionBasis"]={"compositeSnapshot":copy.deepcopy(driver), "optionSnapshot":copy.deepcopy(o), "note":event["note"]}
        g["nodes"].append(decision)
        if driver.get("compositeOf") and driver.get("status")=="candidate":
            driver["status"]="active"   # it is now the real driver; T1 remains in selectionBasis
            for edge in g["edges"]:
                if edge["type"]=="DERIVES" and edge["to"]==driver["id"] and edge["from"]==base:
                    edge["candidate"]=False
        g["edges"].append({"id":"drives-"+decision["id"],"type":"DRIVES","from":driver["id"],"to":decision["id"]})
        g["events"].append(event)
        promoted=[]
        for child in operation.get("children",[]):
            ensure(isinstance(child,dict) and child.get("role") in CHILD_ROLES, "selected child role required")
            if child.get("candidateRequirementId"):
                cid=child["candidateRequirementId"]
                node=next((n for n in g["nodes"] if n["id"]==cid and n["kind"]=="requirement"),None)
                ensure(node is not None and node.get("status") in ("candidate","potential") and not node.get("compositeOf"),
                       "selected candidate child must be a potential R")
                outcomes=[e for e in g["edges"] if e["type"]=="OUTCOME_OF" and e["to"]==cid and not e.get("archived")]
                ensure(len(outcomes)==1 and outcomes[0]["from"]==o["id"],
                       "candidate child belongs to another or multiple possible options")
                ensure(not any(e["type"]=="INTRODUCES" and e["to"]==cid and not e.get("archived") for e in g["edges"]),
                       "candidate child already actual")
                promoted.append({"requirementSnapshot":copy.deepcopy(node),"outcomeEdgeSnapshot":copy.deepcopy(outcomes[0])})
                outcomes[0]["archived"]=True
                node["status"]="active"     # preserve exact ID, preselection QRPE, original work
                node.pop("candidateOnly",None)
            else:
                node=copy.deepcopy(child.get("requirement"))
                ensure(isinstance(node,dict) and node.get("kind")=="requirement" and node.get("id") not in {x["id"] for x in g["nodes"]}, "new child R required")
                node.setdefault("status","active")
                g["nodes"].append(node)
            g["edges"].append({"id":"introduces-"+decision["id"]+"-"+node["id"],"type":"INTRODUCES","from":decision["id"],"to":node["id"],"parent":driver["id"],"childRole":child["role"]})
        if promoted:event["promotedCandidateChildren"]=promoted
        return True
    return False

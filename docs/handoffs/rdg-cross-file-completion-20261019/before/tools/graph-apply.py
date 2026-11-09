#!/usr/bin/env python3
"""Atomic, revision-checked patch application for R-D graph pilot."""
import argparse
import copy
import fcntl
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_GRAPH_ROOT = (ROOT / "graphs").resolve()
KINDS = {"requirement", "decision", "context", "question", "proposal", "option", "action"}
# An explicitly scoped opt-in; old Option/Decision graph semantics remain unchanged.
ACTION_MODEL = "candidate-v6"
# v7 records are optional fields on schemaVersion 1, not a migration of old graphs.
from importlib.machinery import SourceFileLoader
V7 = SourceFileLoader("rdg_v7_model", str(ROOT / "tools" / "rdg-v7-model.py")).load_module()
def reconsider_lib():
    # Legacy schemaVersion-1 harnesses intentionally copy only legacy tools;
    # load the opt-in implementation only for an Action-model operation.
    return SourceFileLoader("rdg_v6_action_reconsider",
        str(ROOT / "tools" / "rdg-v6-action-reconsider.py")).load_module()
EDGE_TYPES = {"DRIVES", "INTRODUCES", "DERIVES", "CONTEXT_FOR", "APPLIES_TO", "OPTION_FOR", "OUTCOME_OF"}


def load_json(path):
    with open(path, encoding="utf-8") as inp:
        return json.load(inp)


def check(condition, message):
    if not condition:
        raise ValueError(message)


def guard_policy(node, event):
    """Material mutation cannot change a protected R's composition by proxy."""
    if not node or node.get('kind') != 'requirement':
        return
    p=node.get('reconsiderationPolicy', {'mode':'ordinary'})
    check(isinstance(p,dict) and p.get('mode','ordinary') in
          ('ordinary','stable','protected'), 'GRAPH_API_INVALID_POLICY')
    if p.get('mode') == 'stable':
        check(isinstance(event.get('reasonForReconsideration'),str) and
              event['reasonForReconsideration'].strip(),
              'GRAPH_API_STABLE_RECONSIDERATION_REASON_REQUIRED')
    if p.get('mode') == 'protected':
        check(event.get('by')=='user' and
              event.get('authorityPrincipal')==p.get('authorityPrincipal'),
              'GRAPH_API_PROTECTED_OWNER_GRANT_REQUIRED')


def validate(graph):
    check(isinstance(graph, dict) and graph.get("schemaVersion") == 1, "schemaVersion must be 1")
    rev = graph.get("revision")
    check(type(rev) is int and rev >= 1, "revision must be positive integer")
    check(all(isinstance(graph.get(k), list) for k in ("nodes", "edges", "events")),
          "nodes, edges, events must all be arrays")
    action_mode = graph.get("actionModel") == ACTION_MODEL
    check(graph.get("actionModel") in (None, ACTION_MODEL), "unsupported actionModel")
    if action_mode:
        check(isinstance(graph.get("identitySpace"), str) and graph["identitySpace"].strip() and
              isinstance(graph.get("rootRequirementId"), str), "action model requires owner and root Requirement")
    nodes = {}
    for n in graph["nodes"]:
        check(isinstance(n, dict) and isinstance(n.get("id"), str) and
              isinstance(n.get("title"), str) and n["title"].strip() and
              n.get("kind") in KINDS, "invalid node")
        check(n["id"] not in nodes, "duplicate node: " + n["id"])
        check(n.get("kind") != "action" or action_mode, "action nodes require candidate-v6 opt-in")
        check(not (action_mode and n.get("kind") in {"option", "decision"}),
              "candidate-v6 graph cannot silently mix Option/Decision with Action")
        if n.get("kind") == "action":
            check(n.get("status") in {"candidate", "selected", "rejected", "superseded"},
                  "invalid action status; performed requires separate outcome contract")
            check(n.get("actionType", "general") in {"general", "decomposition"},
                  "invalid Action type")
            if "canonBlock" in n:
                block = n["canonBlock"]
                check(isinstance(block, dict) and all(isinstance(block.get(k), list)
                      for k in ("recommended", "contraindicated")), "invalid optional Action canonBlock")
                case_ids = set()
                for polarity in ("recommended", "contraindicated"):
                    for case in block[polarity]:
                        check(isinstance(case, dict) and isinstance(case.get("id"), str) and
                              case["id"] and case["id"] not in case_ids and
                              isinstance(case.get("text"), str) and case["text"].strip(),
                              "invalid or duplicate Action canon case")
                        case_ids.add(case["id"])
            if n.get("status") == "selected":
                basis = n.get("selectionBasis")
                check(isinstance(basis, dict) and isinstance(basis.get("driverSnapshot"), dict)
                      and isinstance(basis.get("actionSnapshot"), dict) and
                      basis["actionSnapshot"].get("id") == n["id"] and
                      basis["actionSnapshot"].get("status") == "candidate",
                      "selected Action requires immutable T1 candidate/driver snapshots")
        check(n.get("kind") != "decision" or n.get("status") in {"committed", "superseded"},
              "D must have committed/superseded status; use proposal kind for candidates")
        nodes[n["id"]] = n
    edge_ids = set()
    drivers = {(e.get("from"), e.get("to")) for e in graph["edges"]
               if isinstance(e, dict) and e.get("type") == "DRIVES"}
    graph_links = {node_id: [] for node_id in nodes}
    for e in graph["edges"]:
        check(isinstance(e, dict) and isinstance(e.get("id"), str), "invalid edge id")
        check(e["id"] not in edge_ids, "duplicate edge: " + e["id"])
        edge_ids.add(e["id"])
        check(e.get("type") in EDGE_TYPES, "unsupported edge type: " + str(e.get("type")))
        fr, to = e.get("from"), e.get("to")
        check(fr in nodes and to in nodes, "dangling edge " + e["id"])
        src, dest = nodes[fr]["kind"], nodes[to]["kind"]
        types = {"DRIVES": ("requirement", "decision"),
                 "INTRODUCES": ("decision", "requirement"),
                 "DERIVES": ("requirement", "requirement"),
                 "CONTEXT_FOR": ("context", "decision"),
                 "APPLIES_TO": ("requirement", "requirement"),
                 "OPTION_FOR": ("requirement", "option"),
                 "OUTCOME_OF": ("option", "requirement")}
        legacy_types_match = (src, dest) == types[e["type"]]
        action_types_match = action_mode and (
            (e["type"] == "DRIVES" and (src, dest) == ("requirement", "action")) or
            (e["type"] in {"INTRODUCES", "OUTCOME_OF"} and (src, dest) == ("action", "requirement")) or
            (e["type"] == "CONTEXT_FOR" and (src, dest) == ("context", "action")))
        check(legacy_types_match or action_types_match,
              "incompatible edge kinds: " + e["id"])
        if e["type"] == "APPLIES_TO":
            check(fr != to, "APPLIES_TO cannot reference itself: " + e["id"])
            check(nodes[fr].get("crosscutting") is True,
                  "APPLIES_TO source must be crosscutting Requirement: " + e["id"])
        if e["type"] == "INTRODUCES" and e.get("archived") is not True:
            parent = e.get("parent")
            check(parent in nodes and nodes[parent]["kind"] == "requirement",
                  "INTRODUCES parent must be requirement: " + e["id"])
            check((parent, fr) in drivers, "INTRODUCES parent must drive D: " + e["id"])
            check(nodes[fr].get("status") == ("selected" if action_mode else "committed"),
                  "INTRODUCES requires selected Action or committed D: " + e["id"])
        if action_mode and e["type"] == "OUTCOME_OF" and e.get("archived") is not True:
            check(nodes[fr].get("status") == "candidate" and
                  e.get("childRole") in V7.CHILD_ROLES and
                  (e.get("parent"), fr) in drivers,
                  "potential Action child requires candidate Action, driver and role")
            check(not any(x.get("type") == "INTRODUCES" and x.get("from") == fr and
                          x.get("to") == to and x.get("archived") is not True
                          for x in graph["edges"]), "duplicate potential/actual Action child")
        if e["type"] in {"DRIVES", "INTRODUCES", "DERIVES", "OUTCOME_OF"} and e.get("archived") is not True:
            graph_links[fr].append(to)
    visiting, visited = set(), set()
    def visit(node_id):
        check(node_id not in visiting, "cycle in plan at " + node_id)
        if node_id in visited:
            return
        visiting.add(node_id)
        for next_id in graph_links[node_id]:
            visit(next_id)
        visiting.remove(node_id)
        visited.add(node_id)
    for nid in nodes:
        visit(nid)
    ids = set()
    for event in graph["events"]:
        check(isinstance(event, dict) and isinstance(event.get("id"), str) and
              event["id"] not in ids, "invalid or duplicated event")
        ids.add(event["id"])
        if action_mode and event.get("type") in V7.COMPLETION_EVENTS:
            V7.validate_completion_event(event, nodes)
        elif action_mode and event.get("type") == "action_selected":
            action = nodes.get(event.get("actionId"))
            check(action and action["kind"] == "action" and
                  action.get("status") in ("selected", "superseded"),
                  "action_selected event must identify historically selected Action")
            check(event.get("driverRequirementId") in nodes and
                  nodes[event["driverRequirementId"]]["kind"] == "requirement",
                  "action_selected requires driver Requirement")
        elif action_mode and event.get("type") == "action_requirement_linked":
            action = nodes.get(event.get("actionId"))
            rid = event.get("requirementId")
            check(action and action["kind"] == "action" and
                  action.get("status") in ("selected", "superseded") and
                  rid in nodes and nodes[rid]["kind"] == "requirement" and
                  any(e.get("id") == event.get("edgeId") and
                      e.get("from") == action["id"] and e.get("to") == rid and
                      e.get("type") == "INTRODUCES" for e in graph["edges"]),
                  "invalid shared Action Requirement link history")
        elif action_mode and event.get("type") == "action_withdrawn":
            action = nodes.get(event.get("actionId"))
            check(action and action.get("kind") == "action" and action.get("status") == "superseded" and
                  event.get("driverRequirementId") in nodes and
                  isinstance(event.get("priorActionSnapshot"), dict) and
                  event["priorActionSnapshot"].get("id") == action["id"],
                  "invalid Action withdrawal history")
        elif action_mode and event.get("type") == "action_reconsidered":
            original = nodes.get(event.get("actionId"))
            review = nodes.get(event.get("reviewActionId"))
            check(original and original.get("kind") == "action" and
                  original.get("status") == "superseded" and
                  review and review.get("kind") == "action" and
                  review.get("status") in ("selected", "superseded") and
                  event.get("driverRequirementId") in nodes and
                  isinstance(event.get("approvalRef"), str) and
                  event["approvalRef"].strip() and
                  isinstance(event.get("priorActionSnapshot"), dict) and
                  event["priorActionSnapshot"].get("id") == original["id"] and
                  event["priorActionSnapshot"].get("status") == "selected",
                  "invalid Action reconsideration history")
        elif action_mode and event.get("type") == "graph_changed":
            check(event.get("operation") in {"create_requirement", "create_context", "edit_node",
                  "delete_candidate", "delete_orphan_requirement", "deactivate_requirement",
                  "detach_requirement", "archive_edge", "add_edge", "set_reconsideration_policy",
                  "reparent_requirement", "prepare_action_requirement"} and
                  isinstance(event.get("authorityPrincipal"), str) and event["authorityPrincipal"].strip() and
                  isinstance(event.get("targetId"), str) and event["targetId"],
                  "GRAPH_API_HISTORY_INVALID")
            check(event.get("targetDeleted") is True or event["targetId"] in nodes or
                  any(later.get("type") == "graph_changed" and
                      later.get("operation") in ("delete_candidate", "delete_orphan_requirement") and
                      later.get("targetDeleted") is True and
                      later.get("targetId") == event["targetId"] and
                      isinstance(later.get("priorNodeSnapshot"), dict) and
                      later["priorNodeSnapshot"].get("id") == event["targetId"]
                      for later in graph["events"][graph["events"].index(event)+1:]),
                  "GRAPH_API_HISTORY_TARGET_MISSING")
            check(event.get("targetDeleted") is not True or
                  (event.get("targetId") not in nodes and
                   isinstance(event.get("priorNodeSnapshot"), dict)),
                  "GRAPH_API_DELETION_HISTORY_INVALID")
        elif event.get("type") in {"requirement_deactivated", "requirement_reparented"}:
            check(event.get("requirementId") in nodes and
                  nodes[event["requirementId"]]["kind"] == "requirement",
                  "requirement event refers to missing R")
        else:
            check(event.get("type") in {"decision_selected", "decision_revised"},
                  "unsupported event type")
            check(event.get("decisionId") in nodes and
                  nodes[event["decisionId"]]["kind"] == "decision",
                  "event refers to missing D")
        check(event.get("by") in {"user","assistant"} and isinstance(event.get("note"), str) and
              event["note"].strip(), "decision event needs truthful user/assistant author and material note")
    if action_mode:
        root = nodes.get(graph["rootRequirementId"])
        check(root and root["kind"] == "requirement", "action model root Requirement missing")
        for action in (n for n in nodes.values() if n["kind"] == "action"):
            causes = [e for e in graph["edges"] if e["type"] == "DRIVES"
                      and e["to"] == action["id"] and e.get("archived") is not True]
            check(len(causes) == 1, "Action requires exactly one active driver Requirement")
            if action["status"] == "selected":
                ev = [e for e in graph["events"] if e.get("type") == "action_selected"
                      and e.get("actionId") == action["id"]]
                check(len(ev) == 1 and ev[0].get("driverRequirementId") == causes[0]["from"],
                      "selected Action needs exactly one attributable selection event")
                check(action["selectionBasis"]["driverSnapshot"].get("id") == causes[0]["from"],
                      "Action T1 driver snapshot conflicts with actual driver")
            else:
                check(not any(e.get("type") == "INTRODUCES" and e.get("from") == action["id"]
                              and e.get("archived") is not True for e in graph["edges"]),
                      "only selected Action may introduce actual Requirements")
    if action_mode:
        reconsider_lib().validate_history(graph)
    V7.validate_v7(graph)
    return graph


def apply(original, patch, *, trusted_verified=False):
    check(isinstance(patch, dict) and patch.get("schemaVersion") == 1,
          "patch schemaVersion must be 1")
    check(type(patch.get("expectedRevision")) is int, "expectedRevision must be integer")
    check(patch["expectedRevision"] == original["revision"],
          f"REVISION_CONFLICT expected={patch['expectedRevision']} actual={original['revision']}")
    check(isinstance(patch.get("operations"), list), "patch operations must be array")
    current = copy.deepcopy(original)
    before_ids = {n["id"]: copy.deepcopy(n) for n in current["nodes"]}
    completion_trigger = None
    for operation in patch["operations"]:
        check(isinstance(operation, dict), "invalid operation")
        op = operation.get("op")
        if current.get("actionModel") == ACTION_MODEL:
            # No generic mutation is safe for R/Context/relations in the opt-in
            # model. Require a future event-bearing owner-specific operation.
            allowed = {"add_action", "select_action", "link_action_requirement",
                       "reconsider_action", "withdraw_action", "append_qrpe", "append_finding",
                       "transition_qrpe", "graph_edit", "record_action_execution",
                       "record_requirement_achievement"}
            check(op in allowed,
                  "ACTION_MODEL_GUARD: no untracked R/Context/edge/event mutation")
            if op in {"select_action", "link_action_requirement", "reconsider_action", "withdraw_action", "transition_qrpe", "graph_edit", "record_action_execution", "record_requirement_achievement"}:
                check(trusted_verified is True,
                      "TRUST_REQUIRED: material Action operation requires verified package")
            if op == "append_qrpe":
                issue = operation.get("issue")
                check(isinstance(issue, dict) and issue.get("status") == "open",
                      "ACTION_QRPE_GUARD: new questions start open; transition requires a receipt")
        if op == "graph_edit":
            check(current.get("actionModel") == ACTION_MODEL,
                  "GRAPH_API_REQUIRES_CANDIDATE_V6")
            editor = SourceFileLoader("rdg_graph_api", str(ROOT / "tools" / "rdg-graph-api.py")).load_module()
            editor.apply(current, operation)
        elif op == "add_node":
            n = operation.get("node")
            check(not (current.get("actionModel") == ACTION_MODEL and
                       isinstance(n, dict) and n.get("kind") == "action"),
                  "ACTION_HISTORY_GUARD: use add_action for new Action")
            check(isinstance(n, dict) and n.get("id") not in
                  {x["id"] for x in current["nodes"]}, "add_node: id already exists")
            current["nodes"].append(n)
        elif op == "update_node":
            nid, changes = operation.get("id"), operation.get("changes")
            check(isinstance(changes, dict) and
                  not any(k in changes for k in ("id", "kind")), "unsafe changes")
            node = next((x for x in current["nodes"] if x["id"] == nid), None)
            check(node is not None, "update_node: missing ID")
            # Existing accepted answers are immutable until a dedicated revision
            # operation can retain their previous payload and actual authority.
            old_node = before_ids.get(nid, {})
            if current.get("actionModel") == ACTION_MODEL and old_node.get("kind") == "action":
                check(not changes, "ACTION_HISTORY_GUARD: modify Action via dedicated event-bearing operation")
            if current.get("actionModel") == ACTION_MODEL and old_node.get("kind") == "requirement":
                check(not (set(changes) & {"title", "status", "active", "requirementText", "scope"}),
                      "REQUIREMENT_HISTORY_GUARD: normative R revision requires dedicated provenance")
            if old_node.get("kind") == "decision" and old_node.get("status") in {"committed", "superseded"}:
                verification_fields = {"evidenceStatus", "achievement", "verification", "openQuestion"}
                changed_keys = {key for key, value in changes.items()
                                if key not in node or node[key] != value}
                check(changed_keys <= verification_fields,
                      "DECISION_HISTORY_GUARD: accepted D content/status/scope cannot be overwritten; "
                      "only verification fields may change")
            # Material QRPE/composite history is append-only. T1 must not be edited
            # as if knowledge discovered at T2 had been known when D was selected.
            check(not (set(changes) & {"qrpe", "history", "compositeOf", "selectionBasis",
                                       "selectedOptionId", "canonBlock", "preparedSource", "currentStatement",
                                       "contextFieldRef", "contextValue", "contextAnswers", "contextMapping", "contextUses"}),
                  "HISTORY_GUARD: use material v7 operations for QRPE, composites and canons")
            if old_node.get("contextFieldRef"):
                check(not (set(changes)-{"verification","openQuestion"}), "CONTEXT_OWNER_GUARD: use set_context_value")
            node.update(changes)
        elif op == "add_edge":
            e = operation.get("edge")
            check(not (current.get("actionModel") == ACTION_MODEL and
                       isinstance(e, dict) and e.get("type") == "INTRODUCES" and
                       any(n["id"] == e.get("from") and n.get("kind") == "action"
                           for n in current["nodes"])),
                  "ACTION_HISTORY_GUARD: use event-bearing Action operation for introduced R")
            check(isinstance(e, dict) and e.get("id") not in
                  {x["id"] for x in current["edges"]}, "add_edge: id already exists")
            current["edges"].append(e)
        elif op == "revise_decision":
            nid = operation.get("id")
            old = next((n for n in current["nodes"] if n["id"] == nid), None)
            new = copy.deepcopy(operation.get("decision"))
            event = copy.deepcopy(operation.get("event"))
            check(old and old["kind"] == "decision" and old.get("status") == "committed",
                  "revise_decision: current committed D required")
            check(isinstance(new, dict) and new.get("kind") == "decision" and
                  new.get("status") == "committed" and new.get("id") not in {n["id"] for n in current["nodes"]},
                  "revise_decision: a new committed D identity is required")
            check(isinstance(event, dict) and event.get("type") == "decision_revised" and
                  event.get("decisionId") == new["id"] and event.get("previousDecisionId") == nid and
                  event.get("by") in {"user","assistant"} and isinstance(event.get("note"), str) and event["note"].strip(),
                  "revise_decision: explicit revision authority required")
            check(event.get("id") not in {e["id"] for e in current["events"]}, "duplicate revision event")
            previous = copy.deepcopy(old)
            prior_edges = [copy.deepcopy(e) for e in current["edges"] if e.get("from") == nid or e.get("to") == nid]
            drivers = [e for e in prior_edges if e["type"] == "DRIVES" and e["to"] == nid and not e.get("archived")]
            check(drivers, "revise_decision: old D has no actual driver")
            event["previousDecisionSnapshot"] = previous
            event["previousEdges"] = prior_edges
            event["driverSnapshots"] = [copy.deepcopy(n) for n in current["nodes"] if n["id"] in {e["from"] for e in drivers}]
            old.update(status="superseded", supersededBy=new["id"], supersededEventId=event["id"])
            for e in current["edges"]:
                if e.get("from") == nid or e.get("to") == nid:
                    e["archived"] = True
            current["nodes"].append(new)
            for e in drivers:
                current["edges"].append({**e, "id": e["id"]+"-revision-"+new["id"], "to":new["id"], "archived":False})
            for e in operation.get("edges", []):
                check(e.get("from") == new["id"] and e.get("type") == "INTRODUCES", "revision edges must introduce through new D")
                current["edges"].append(copy.deepcopy(e))
            current["events"].append(event)
        elif op == "add_action":
            check(current.get("actionModel") == ACTION_MODEL,
                  "add_action requires candidate-v6 graph")
            action = copy.deepcopy(operation.get("action"))
            rid = operation.get("requirementId")
            check(isinstance(action, dict) and action.get("kind") == "action" and
                  action.get("status") == "candidate" and
                  isinstance(action.get("id"), str) and action["id"] and
                  isinstance(action.get("title"), str) and action["title"].strip(),
                  "add_action requires candidate Action")
            check(any(n["kind"] == "requirement" and n["id"] == rid and
                      n.get("status") not in ("inactive", "superseded") and n.get("active") is not False
                      for n in current["nodes"]), "active driver Requirement missing")
            check(all(n["id"] != action["id"] for n in current["nodes"]), "Action ID collision")
            current["nodes"].append(action)
            current["edges"].append({"id": "action-drive-" + action["id"],
                "type": "DRIVES", "from": rid, "to": action["id"]})
        elif op == "select_action":
            check(current.get("actionModel") == ACTION_MODEL,
                  "select_action requires candidate-v6 graph")
            action = next((n for n in current["nodes"] if n.get("kind") == "action"
                           and n["id"] == operation.get("actionId")), None)
            check(action and action["status"] == "candidate", "Action must be a current candidate")
            driving = [e for e in current["edges"] if e["type"] == "DRIVES" and
                       e["to"] == action["id"] and e.get("archived") is not True]
            check(len(driving) == 1, "Action driver must be unambiguous")
            driver = next(n for n in current["nodes"] if n["id"] == driving[0]["from"])
            event = copy.deepcopy(operation.get("event"))
            check(isinstance(event, dict) and event.get("type") == "action_selected" and
                  event.get("actionId") == action["id"] and
                  event.get("driverRequirementId") == driver["id"] and
                  event.get("by") in {"user", "assistant"} and
                  isinstance(event.get("note"), str) and event["note"].strip() and
                  isinstance(event.get("id"), str) and event["id"] and
                  event["id"] not in {e["id"] for e in current["events"]},
                  "Action selection needs unique attributed material event")
            prepared = [e for e in current["edges"] if e.get("type") == "OUTCOME_OF" and
                        e.get("from") == action["id"] and e.get("archived") is not True]
            if operation.get('children') or prepared:
                guard_policy(driver,event)
            if action.get("actionType") == "decomposition":
                check(any(e.get("childRole") == "subgoal" for e in prepared) or
                      any(c.get("role") == "subgoal" for c in operation.get("children", [])),
                      "decomposition Action requires at least one subgoal")
            action["selectionBasis"] = {
                "driverSnapshot": copy.deepcopy(driver),
                "actionSnapshot": copy.deepcopy(action),
                "note": event["note"]
            }
            action["status"] = "selected"
            if prepared:
                event["preparedChildrenSnapshot"] = [copy.deepcopy(e) for e in prepared]
            for edge in prepared:
                requirement = next(n for n in current["nodes"] if n["id"] == edge["to"])
                guard_policy(requirement, event)
                check(requirement.get("active") is not False and
                      requirement.get("status", "active") in {"candidate", "potential", "active"},
                      "prepared child is no longer available")
                check(requirement.get("projectionOf") is None,
                      "select prepared child through its owning graph")
                if requirement.get("status") in {"candidate", "potential"}:
                    requirement["status"] = "active"
                edge["type"] = "INTRODUCES"
            current["events"].append(event)
            for child in operation.get("children", []):
                check(isinstance(child, dict) and child.get("role") in {"subgoal", "method_correctness"},
                      "selected Action child role required")
                requirement = copy.deepcopy(child.get("requirement"))
                check(isinstance(requirement, dict) and requirement.get("kind") == "requirement"
                      and isinstance(requirement.get("id"), str) and requirement["id"] and
                      isinstance(requirement.get("title"), str) and requirement["title"].strip() and
                      requirement["id"] not in {n["id"] for n in current["nodes"]},
                      "selected child requires new Requirement")
                check(requirement.get("status", "active") == "active" and
                      requirement.get("projectionOf") is None,
                      "selected Action introduces owning active Requirement only")
                requirement.setdefault("status", "active")
                current["nodes"].append(requirement)
                current["edges"].append({"id": "action-introduces-"+action["id"]+"-"+requirement["id"],
                    "type": "INTRODUCES", "from": action["id"], "to": requirement["id"],
                    "parent": driver["id"], "childRole": child["role"]})
        elif op == "link_action_requirement":
            check(current.get("actionModel") == ACTION_MODEL,
                  "link_action_requirement requires candidate-v6 graph")
            aid, rid = operation.get("actionId"), operation.get("requirementId")
            ns = {n["id"]: n for n in current["nodes"]}
            action, target = ns.get(aid), ns.get(rid)
            drivers = [e for e in current["edges"] if e.get("type") == "DRIVES" and
                       e.get("to") == aid and e.get("archived") is not True]
            check(action and action.get("kind") == "action" and
                  action.get("status") == "selected" and
                  target and target.get("kind") == "requirement" and
                  target.get("status", "active") == "active" and
                  not target.get("projectionOf") and
                  len(drivers) == 1 and rid != drivers[0]["from"],
                  "ACTION_LINK_REQUIRES_SELECTED_ACTION_AND_EXISTING_ACTIVE_R")
            check(not any(e.get("type") == "INTRODUCES" and
                          e.get("from") == aid and e.get("to") == rid and
                          e.get("archived") is not True for e in current["edges"]),
                  "ACTION_LINK_DUPLICATE")
            edge_id, role = operation.get("edgeId"), operation.get("childRole")
            check(isinstance(edge_id, str) and edge_id and
                  all(e["id"] != edge_id for e in current["edges"]) and
                  role in ("subgoal", "method_correctness"),
                  "ACTION_LINK_REQUIRES_UNIQUE_EDGE_AND_ROLE")
            event = copy.deepcopy(operation.get("event"))
            check(isinstance(event, dict) and
                  event.get("type") == "action_requirement_linked" and
                  event.get("actionId") == aid and event.get("requirementId") == rid and
                  event.get("edgeId") == edge_id and
                  event.get("driverRequirementId") == drivers[0]["from"] and
                  event.get("by") in ("user", "assistant") and
                  isinstance(event.get("note"), str) and event["note"].strip() and
                  isinstance(event.get("id"), str) and event["id"] and
                  event["id"] not in {e["id"] for e in current["events"]},
                  "ACTION_LINK_REQUIRES_ATTRIBUTED_EVENT")
            guard_policy(target,event)
            guard_policy(ns.get(drivers[0]['from']),event)
            current["edges"].append({"id": edge_id, "type": "INTRODUCES",
                "from": aid, "to": rid, "parent": drivers[0]["from"],
                "childRole": role})
            current["events"].append(event)
        elif op == "withdraw_action":
            ns = {n["id"]: n for n in current["nodes"]}
            aid = operation.get("actionId")
            for edge in current["edges"]:
                if edge.get("archived") is not True and (
                    edge["type"] == "DRIVES" and edge["to"] == aid or
                    edge["type"] == "INTRODUCES" and edge["from"] == aid):
                    guard_policy(ns.get(edge["from"]), operation.get("event") or {})
                    guard_policy(ns.get(edge["to"]), operation.get("event") or {})
            reconsider_lib().withdraw(current, operation)
        elif op == "reconsider_action":
            check(trusted_verified is True,
                  "TRUST_REQUIRED: use writer package with verified approval and evidence")
            ns={n['id']:n for n in current['nodes']}
            old_id=operation.get('actionId')
            driver_ids=[e['from'] for e in current['edges'] if e.get('type')=='DRIVES' and
                        e.get('to')==old_id and e.get('archived') is not True]
            for rid in driver_ids:
                guard_policy(ns.get(rid),operation.get('event') or {})
            for edge in current['edges']:
                if edge.get('type')=='INTRODUCES' and edge.get('from')==old_id and edge.get('archived') is not True:
                    guard_policy(ns.get(edge['to']),operation.get('event') or {})
            reconsider_lib().apply(current, operation)
        elif op in {"record_action_execution", "record_requirement_achievement"}:
            V7.record_completion(current, operation)
        elif op == "append_event":
            e = operation.get("event")
            check(isinstance(e, dict) and e.get("id") not in
                  {x["id"] for x in current["events"]}, "append_event: id already exists")
            current["events"].append(e)
        elif V7.apply_v7_operation(current, operation):
            pass
        else:
            raise ValueError("unsupported operation: " + str(op))
        if current.get("actionModel") == ACTION_MODEL and op in {"select_action", "link_action_requirement", "withdraw_action", "graph_edit", "record_action_execution", "record_requirement_achievement"}:
            trigger = next((e for e in reversed(current["events"]) if e.get("id") == (operation.get("event") or {}).get("id")), None)
            if trigger and trigger.get("authorityPrincipal"):
                from datetime import datetime, timezone
                trigger.setdefault("recordedAt", datetime.now(timezone.utc).isoformat())
                completion_trigger = trigger
    new_committed = {n["id"] for n in current["nodes"] if n["kind"] == "decision"
                     and n.get("status") == "committed" and
                     (n["id"] not in before_ids or before_ids[n["id"]].get("status") != "committed")}
    selected = {e.get("decisionId") for e in current["events"] if
                e.get("type") in {"decision_selected", "decision_revised"}}
    check(new_committed <= selected, "new committed Decision requires decision_selected event")
    validate(current)
    V7.validate_completion_write(current)
    if completion_trigger:
        V7.append_derived_completion(current, completion_trigger)
        validate(current)
    if current == original:
        return current, False
    current["revision"] += 1
    return current, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph")
    parser.add_argument("--patch", required=True)
    parser.add_argument("--package", action="store_true", help="Apply a transactionId + graph changes package")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    patch = load_json(Path(args.patch).resolve())
    if not args.package:
        check(args.graph is not None, "--graph is required for a single-file patch")
        graph_path = Path(args.graph).resolve()
        check(graph_path.is_relative_to(ALLOWED_GRAPH_ROOT) and graph_path.name == "graph.json",
              "graph must be graphs/<group>/<slug>/graph.json inside this project")
        disk_graph = load_json(graph_path)
        check(disk_graph.get("readOnly") is not True, "READ_ONLY_GRAPH: reference examples cannot be updated")
        check(graph_path.is_relative_to((ALLOWED_GRAPH_ROOT / "workspaces").resolve()),
              "NON_WORKSPACE_GRAPH: only workspace graphs may be changed")
        patch = {"schemaVersion":1, "changes":[{"file":graph_path.relative_to(ALLOWED_GRAPH_ROOT).as_posix(), "patch":patch}]}
    from importlib.machinery import SourceFileLoader
    package = SourceFileLoader("rdg_graph_package", str(ROOT / "tools" / "graph-package.py")).load_module()
    package.execute(patch, dry_run=args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        import sys
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(2)

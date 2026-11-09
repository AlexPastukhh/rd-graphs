#!/usr/bin/env python3
"""Read-only draft Finding leads from Stage 3P's assumption-bound temporal report.

The output is never a confirmed F-P, never a graph mutation, and never an
automatically accepted Finding, Proposal or Action.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path


def require(ok, reason):
    if not ok:
        raise ValueError("FINDING_DRAFT_" + reason)


def build(report):
    require(isinstance(report, dict) and
            report.get("readOnly") is True and
            report.get("planStatus") == "candidate" and
            report.get("committedFindings") == [] and
            report.get("selectedActions") == [] and
            report.get("executionPerformed") is False,
            "REQUIRES_READ_ONLY_CANDIDATE_PLAN_IMPACT")
    require(isinstance(report.get("planId"), str) and report["planId"] and
            type(report.get("planRevision")) is int and
            report["planRevision"] >= 1 and
            isinstance(report.get("branches"), list), "INVALID_SOURCE_REPORT")
    drafted, used = [], set()
    for branch in report["branches"]:
        require(isinstance(branch, dict) and
                isinstance(branch.get("actionReviewLeads"), list),
                "INVALID_BRANCH")
        for lead in branch["actionReviewLeads"]:
            require(isinstance(lead, dict) and
                    isinstance(lead.get("action"), dict),
                    "INVALID_LEAD")
            if not lead.get("timeConflictReview"):
                continue
            action, source = lead["action"], lead.get("dependencyDigest")
            require(isinstance(source, str) and
                    re.fullmatch("[0-9a-f]{64}", source) and
                    isinstance(lead.get("stepId"), str) and lead["stepId"] and
                    isinstance(action.get("graphFile"), str) and
                    isinstance(action.get("actionId"), str) and
                    isinstance(action.get("identitySpace"), str) and
                    isinstance(lead.get("deadlineChecks"), list) and
                    any(c.get("comparison") == "candidate-plan-hard-constraint-conflict"
                        and c.get("assumptionOnly") is True
                        for c in lead["deadlineChecks"]),
                    "CONFLICT_UNSUPPORTED")
            key = (branch.get("branchId"), branch.get("outcome"),
                   lead["stepId"], action["graphFile"], action["actionId"])
            require(key not in used, "DUPLICATE_LEAD")
            used.add(key)
            key_bytes = json.dumps(key, sort_keys=True, ensure_ascii=False).encode()
            ident = "F-R-TEMP-" + hashlib.sha256(key_bytes + source.encode()).hexdigest()[:16]
            context = {
                "planId": report["planId"],
                "planRevision": report["planRevision"],
                "stepId": lead["stepId"],
                "branchId": branch.get("branchId"),
                "outcome": branch.get("outcome"),
                "dependencyDigest": source,
                "status": "candidate",
            }
            draft = {
                "id": ident,
                "text": ("Possible schedule risk for Action " + action["actionId"] +
                         " in candidate Temporal Plan " + report["planId"] +
                         "; check whether the assumed constraints are real."),
                "status": "open", "findingType": "F-R",
                "findingScope": "UPSTREAM",
                "questions": [
                    "Are the source Plan deadlines and notBefore assumptions authorized and applicable?",
                    "Is this branch relevant, and what real duration/resources would the Action require?",
                ],
                "evidenceRefs": [], "proposalRefs": [],
                "temporalContext": context,
            }
            drafted.append({
                "reviewStatus": "draft-only-not-verified",
                "targetGraphFile": action["graphFile"],
                "targetIdentitySpace": action["identitySpace"],
                "targetActionId": action["actionId"],
                "suggestedFinding": draft,
                "sourceComparisons": [c for c in lead["deadlineChecks"]
                    if c.get("comparison") == "candidate-plan-hard-constraint-conflict"],
                "commitAllowedAutomatically": False,
            })
    return {
        "sourcePlanId": report["planId"],
        "sourcePlanRevision": report["planRevision"],
        "readOnly": True, "committedFindings": [], "acceptedProposals": [],
        "selectedActions": [], "draftCount": len(drafted), "reviewDrafts": drafted,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--impact-report", required=True, type=Path)
    args = parser.parse_args()
    report = json.loads(args.impact_report.read_text(encoding="utf8"))
    print(json.dumps(build(report), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        import sys
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)

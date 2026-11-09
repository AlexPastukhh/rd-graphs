"""One-command Sonar READ -> detailed report -> owner ASK scenario for Fortis Repo.

Runs only through the pinned typed Repo client. It never reads a Sonar token,
chooses a project, approves an action, or sends a Sonar mutation.
"""
import argparse
import json
import re
import sys
import uuid

from . import repo_sonar_tools

ORGANIZATION = "alexpastukhh"
PROJECT = "AlexPastukhh_obs-planning-docs"
OWNER_PORTAL = "http://localhost:19103"
ISSUE_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")


class ScenarioError(Exception):
    """Safe, stable error token for scenario preconditions."""


def _request_id(value=None):
    ident = value or str(uuid.uuid4())
    try:
        parsed = str(uuid.UUID(ident))
    except (TypeError, ValueError, AttributeError):
        raise ScenarioError("FORTIS_SCENARIO_REQUEST_ID_INVALID") from None
    if parsed != ident:
        raise ScenarioError("FORTIS_SCENARIO_REQUEST_ID_INVALID")
    return ident


def _data(response, operation):
    if (type(response) is not dict or response.get("service") != "sonarcloud" or
            response.get("operation") != operation or type(response.get("data")) is not dict):
        raise ScenarioError("FORTIS_SCENARIO_READ_RESPONSE_INVALID")
    return response["data"]


def review_issue(issue_key, reason, *, request_id=None, call=None):
    """Read the pinned project, report current quality/issues, then create ASK."""
    invoke = call or repo_sonar_tools.call
    if type(issue_key) is not str or not ISSUE_KEY.fullmatch(issue_key):
        raise ScenarioError("FORTIS_SCENARIO_ISSUE_KEY_INVALID")
    if type(reason) is not str or not 1 <= len(reason.strip()) <= 1500:
        raise ScenarioError("FORTIS_SCENARIO_REASON_INVALID")
    ident = _request_id(request_id)

    projects = _data(invoke("sonar.list_projects", target=ORGANIZATION,
                            page=1, page_size=100), "list_projects")
    rows = projects.get("projects")
    if (type(rows) is not list or
            not any(type(row) is dict and row.get("key") == PROJECT for row in rows)):
        raise ScenarioError("FORTIS_SCENARIO_PINNED_PROJECT_NOT_VISIBLE")

    issues = _data(invoke("sonar.list_issues", target=PROJECT,
                          page=1, page_size=100), "list_issues")
    if (issues.get("projectKey") != PROJECT or type(issues.get("issues")) is not list or
            type(issues.get("total")) is not int):
        raise ScenarioError("FORTIS_SCENARIO_ISSUE_LIST_INVALID")

    quality = _data(invoke("sonar.get_quality_gate", target=PROJECT),
                    "get_quality_gate")
    if quality.get("projectKey") != PROJECT or type(quality.get("conditions")) is not list:
        raise ScenarioError("FORTIS_SCENARIO_QUALITY_GATE_INVALID")

    detail = _data(invoke("sonar.get_issue", target=issue_key,
                          project_key=PROJECT), "get_issue")
    issue = detail.get("issue")
    if (detail.get("projectKey") != PROJECT or type(issue) is not dict or
            issue.get("key") != issue_key or issue.get("projectKey") != PROJECT):
        raise ScenarioError("FORTIS_SCENARIO_TARGET_ISSUE_INVALID")
    if issue.get("status") not in ("OPEN", "CONFIRMED"):
        raise ScenarioError("FORTIS_SCENARIO_TARGET_ISSUE_NOT_ACCEPTABLE")

    # This is a typed Fortis action request. It does NOT call Sonar POST.
    proposal = invoke("sonar.propose_accept_issue", target=issue_key,
                      project_key=PROJECT, reason=reason, request_id=ident)
    if (type(proposal) is not dict or proposal.get("requestId") != ident or
            proposal.get("state") not in repo_sonar_tools._STATES):
        raise ScenarioError("FORTIS_SCENARIO_ASK_RESPONSE_INVALID")
    sample = []
    for row in issues["issues"][:10]:
        if type(row) is not dict:
            raise ScenarioError("FORTIS_SCENARIO_ISSUE_LIST_INVALID")
        sample.append({key: row.get(key) for key in (
            "key", "status", "severity", "type", "rule", "message",
            "component", "line", "updateDate")})
    return {
        "scenario": "sonar-read-report-owner-ask",
        "organization": ORGANIZATION,
        "project": PROJECT,
        "report": {
            "projects_visible": len(rows),
            "issues_total": issues["total"],
            "issues_returned": len(issues["issues"]),
            "issues_page": issues.get("page"),
            "issues_page_size": issues.get("pageSize"),
            "issues_has_more": issues.get("hasMore"),
            "issues_coverage": issues.get("coverage"),
            "issue_sample": sample,
            "quality_gate": {
                "status": quality.get("status"),
                "conditions": quality["conditions"],
                "scope": quality.get("scope"),
                "pr_sha_binding": quality.get("prShaBinding"),
            },
            "target_issue": {key: issue.get(key) for key in (
                "key", "status", "severity", "type", "rule", "message",
                "component", "line", "updateDate")},
        },
        "approval": {
            "request_id": ident,
            "state": proposal["state"],
            "operation": "sonarcloud.accept_issue",
            "owner_portal": OWNER_PORTAL,
            "next_step": "Owner reviews exact frozen issue and decides; AI cannot approve.",
        },
    }


def request_status(request_id, *, call=None):
    invoke = call or repo_sonar_tools.call
    ident = _request_id(request_id)
    result = invoke("approvals.request_status", request_id=ident)
    if (type(result) is not dict or result.get("requestId") != ident or
            result.get("state") not in repo_sonar_tools._STATES):
        raise ScenarioError("FORTIS_SCENARIO_STATUS_RESPONSE_INVALID")
    return {"request_id": ident, "state": result["state"]}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Pinned Sonar READ/report -> Fortis owner ASK (no Sonar WRITE)")
    sub = parser.add_subparsers(dest="command", required=True)
    review = sub.add_parser("review")
    review.add_argument("--issue-key", required=True)
    review.add_argument("--reason", required=True)
    review.add_argument("--request-id")
    status = sub.add_parser("status")
    status.add_argument("--request-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "review":
            ident = _request_id(args.request_id)
            # Print before the mutating-to-Fortis (but non-Sonar) ASK call so
            # the same ID can be reused after a lost client response.
            print("FORTIS_REQUEST_ID=" + ident, file=sys.stderr, flush=True)
            result = review_issue(args.issue_key, args.reason, request_id=ident)
        else:
            result = request_status(args.request_id)
    except (ScenarioError, repo_sonar_tools.Denied) as exc:
        print("FORTIS_SCENARIO_DENIED=" + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

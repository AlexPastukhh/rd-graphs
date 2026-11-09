"""Offline tests for the one-command Sonar -> report -> owner ASK scenario."""
import unittest
import uuid

from fortis_approvals import sonar_review_scenario as scenario


PROJECT = scenario.PROJECT
ISSUE = PROJECT + "-I007"
REQUEST_ID = "00000000-0000-4000-8000-000000000007"


def fixture_call(*, issue_status="OPEN", visible=True, proposal_state="PENDING"):
    calls = []
    def invoke(tool, **kwargs):
        calls.append((tool, kwargs))
        if tool == "sonar.list_projects":
            projects = [{"key": PROJECT}] if visible else []
            return {"service": "sonarcloud", "operation": "list_projects",
                    "data": {"projects": projects}}
        if tool == "sonar.list_issues":
            return {"service": "sonarcloud", "operation": "list_issues",
                    "data": {"projectKey": PROJECT, "issues": [{
                        "key": ISSUE, "status": issue_status,
                        "severity": "MAJOR", "type": "BUG", "rule": "python:S1234",
                        "message": "Example finding", "component": "src/app.py",
                        "line": 42, "updateDate": "2026-11-02T10:00:00+0000"}],
                        "total": 1, "page": 1, "pageSize": 100,
                        "hasMore": False, "coverage": "LIVE_PAGE_NOT_CROSS_PAGE_SNAPSHOT"}}
        if tool == "sonar.get_quality_gate":
            return {"service": "sonarcloud", "operation": "get_quality_gate",
                    "data": {"projectKey": PROJECT, "status": "ERROR",
                             "conditions": [{"status": "ERROR", "metricKey": "new_violations"}],
                             "scope": "CURRENT_DEFAULT_BRANCH",
                             "prShaBinding": "NOT_VERIFIED_D2"}}
        if tool == "sonar.get_issue":
            return {"service": "sonarcloud", "operation": "get_issue",
                    "data": {"projectKey": PROJECT, "issue": {
                        "key": ISSUE, "projectKey": PROJECT, "status": issue_status,
                        "severity": "MAJOR", "type": "BUG", "rule": "python:S1234",
                        "message": "Example finding", "component": "src/app.py",
                        "line": 42, "updateDate": "2026-11-02T10:00:00+0000"}}}
        if tool == "sonar.propose_accept_issue":
            return {"requestId": kwargs["request_id"], "state": proposal_state}
        if tool == "approvals.request_status":
            return {"requestId": kwargs["request_id"], "state": "REJECTED"}
        raise AssertionError("unexpected tool: " + tool)
    return invoke, calls


class SonarReviewScenarioTests(unittest.TestCase):
    def test_reads_report_and_submits_exactly_one_owner_ask(self):
        invoke, calls = fixture_call()
        result = scenario.review_issue(
            ISSUE, "Please review this exact issue", request_id=REQUEST_ID,
            call=invoke)
        self.assertEqual([item[0] for item in calls], [
            "sonar.list_projects", "sonar.list_issues", "sonar.get_quality_gate",
            "sonar.get_issue", "sonar.propose_accept_issue"])
        self.assertEqual(calls[-1][1], {
            "target": ISSUE, "project_key": PROJECT,
            "reason": "Please review this exact issue", "request_id": REQUEST_ID})
        self.assertEqual(result["approval"]["state"], "PENDING")
        self.assertEqual(result["approval"]["request_id"], REQUEST_ID)
        self.assertEqual(result["report"]["quality_gate"]["scope"],
                         "CURRENT_DEFAULT_BRANCH")
        self.assertEqual(result["report"]["target_issue"]["line"], 42)
        self.assertEqual(result["report"]["issues_total"], 1)

    def test_owner_reject_status_is_read_back_by_same_request_id(self):
        invoke, calls = fixture_call()
        result = scenario.request_status(REQUEST_ID, call=invoke)
        self.assertEqual(result, {"request_id": REQUEST_ID, "state": "REJECTED"})
        self.assertEqual(calls, [("approvals.request_status",
                                  {"request_id": REQUEST_ID})])

    def test_unlisted_project_fails_before_issue_or_ask(self):
        invoke, calls = fixture_call(visible=False)
        with self.assertRaisesRegex(
                scenario.ScenarioError, "PINNED_PROJECT_NOT_VISIBLE"):
            scenario.review_issue(ISSUE, "review", call=invoke)
        self.assertEqual([item[0] for item in calls], ["sonar.list_projects"])

    def test_non_open_issue_fails_before_ask(self):
        invoke, calls = fixture_call(issue_status="ACCEPTED")
        with self.assertRaisesRegex(
                scenario.ScenarioError, "TARGET_ISSUE_NOT_ACCEPTABLE"):
            scenario.review_issue(ISSUE, "review", call=invoke)
        self.assertNotIn("sonar.propose_accept_issue",
                         [item[0] for item in calls])
    def test_invalid_issue_and_request_ids_fail_without_network(self):
        invoke, calls = fixture_call()
        for value in ("", "../foreign", "https://example.invalid", "A" * 129):
            with self.subTest(value=value), self.assertRaises(
                    scenario.ScenarioError):
                scenario.review_issue(value, "review", call=invoke)
        with self.assertRaisesRegex(
                scenario.ScenarioError, "REQUEST_ID_INVALID"):
            scenario.request_status("not-a-uuid", call=invoke)
        self.assertEqual(calls, [])

    def test_generated_request_id_is_canonical_uuid(self):
        invoke, calls = fixture_call()
        result = scenario.review_issue(ISSUE, "review", call=invoke)
        ident = result["approval"]["request_id"]
        self.assertEqual(str(uuid.UUID(ident)), ident)
        self.assertEqual(calls[-1][1]["request_id"], ident)

    def test_retry_with_same_request_id_reports_existing_terminal_state(self):
        invoke, _ = fixture_call(proposal_state="REJECTED")
        result = scenario.review_issue(
            ISSUE, "review", request_id=REQUEST_ID, call=invoke)
        self.assertEqual(result["approval"]["state"], "REJECTED")


if __name__ == "__main__":
    unittest.main()

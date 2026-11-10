#!/usr/bin/env python3
"""Synthetic stdio fixture only. Optional execution uses disposable test owners."""
import argparse
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
M = SourceFileLoader("rdg_webauthn_fixture", str(ROOT / "tools/rdg-webauthn.py")).load_module()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-fixture", action="store_true", required=True)
    parser.add_argument("--origin", required=True)
    args = parser.parse_args()
    clock = [0.0]
    verifier = M.Verifier("localhost", args.origin, clock=lambda: clock[0])
    principal = "synthetic-operator"
    current_digest = ["1" * 64]
    execution = None
    fields = {"register_begin": set(),
              "register_complete": {"ceremonyId", "response"},
              "decision_begin": {"decision"},
              "decision_complete": {"ceremonyId", "response"},
              "advance_clock": {"seconds"}, "change_preview": {"digest"},
              "unknown_principal": set(), "summary": set(),
              "execution_setup": {"operation"}, "execution_begin": {"decision"},
              "execution_complete": {"ceremonyId", "response"},
              "execution_new_plan": set(), "execution_replay": set(),
              "execution_recover": set(), "execution_summary": set()}
    for line in sys.stdin:
        request = None
        try:
            request = json.loads(line)
            method, body = request["method"], request.get("body", {})
            if method not in fields or not isinstance(body, dict) or set(body) != fields[method]:
                raise ValueError("SYNTHETIC_MESSAGE_FIELDS")
            if method.startswith("execution_") and method != "execution_setup" and execution is None:
                raise ValueError("SYNTHETIC_EXECUTION_NOT_READY")
            if method == "register_begin":
                result = verifier.begin_registration(principal, "Synthetic operator")
            elif method == "register_complete":
                result = verifier.complete_registration(body["ceremonyId"], body["response"])
            elif method == "decision_begin":
                result = verifier.begin_decision(principal, current_digest[0], body["decision"])
            elif method == "decision_complete":
                result = verifier.complete_decision(body["ceremonyId"], body["response"], current_digest[0])
            elif method == "advance_clock":
                clock[0] += body["seconds"]
                result = {"clockAdvanced": True}
            elif method == "change_preview":
                current_digest[0] = body["digest"]
                result = {"previewChanged": True}
            elif method == "unknown_principal":
                result = verifier.begin_decision("unregistered", current_digest[0], "approve")
            elif method == "execution_setup":
                if body["operation"] not in ("edit", "replace", "crash"):
                    raise ValueError("SYNTHETIC_OPERATION")
                if execution is not None:
                    execution.doCleanups()
                tests = SourceFileLoader("webauthn_execution_fixture",
                    str(ROOT / "tests/rdg-approval-execution.test.py")).load_module()
                execution = tests.ApprovalExecution(
                    "test_exact_signed_execution_separates_three_actors_without_granting_ai")
                execution.setUp()
                execution.executor = execution.bridge(execution.human, verifier=verifier)
                execution.mode = body["operation"]
                if execution.mode == "replace":
                    execution.target = execution.create("native-target")
                    source = execution.create("native-source", "ready")
                    p1 = execution.create("native-P1")
                    execution.app().request(execution.placement(p1, execution.target))
                    execution.request_body = execution.replace_request(execution.target, source)
                else:
                    execution.target = execution.locked()
                    execution.request_body = execution.edit(execution.target)
                execution.pending(execution.request_body)
                result = {"requestId": execution.request_body["transactionId"],
                          "initiatorGrantId": execution.grant_id,
                          "executorGrantId": execution.human_grant}
            elif method == "execution_begin":
                result = execution.executor.begin(execution.request_body["transactionId"],
                                                  body["decision"])
            elif method == "execution_complete":
                def failpoint(stage):
                    if execution.mode == "crash" and stage == "prepared":
                        raise ValueError("SYNTHETIC_AFTER_ACCEPTANCE")
                result = execution.executor.complete(body["ceremonyId"], body["response"],
                                                      failpoint=failpoint)
            elif method == "execution_new_plan":
                if execution.mode != "replace":
                    raise ValueError("SYNTHETIC_REPLACE_ONLY")
                p2 = execution.create("native-P2")
                execution.app().request(execution.placement(p2, execution.target))
                result = {"addedPlanPackageId": p2}
            elif method == "execution_replay":
                result = execution.app().request(execution.request_body)
            elif method == "execution_recover":
                result = execution.app().recover(execution.request_body["transactionId"])
            elif method == "execution_summary":
                current = execution.current(execution.target)
                result = {"graph": current["graph"],
                          "state": execution.app().approval_read(
                              execution.request_body["transactionId"])["state"],
                          "realHumanProof": False, "syntheticOwnersOnly": True}
            else:
                result = {"credentialCount": len(verifier._credentials),
                          "noGraphWriterConnected": execution is None,
                          "realHumanProof": False}
            reply = {"id": request["id"], "ok": True, "result": result}
        except (ValueError, TypeError, KeyError) as exc:
            reply = {"id": request.get("id") if isinstance(request, dict) else None,
                     "ok": False, "error": str(exc)}
        print(json.dumps(reply, ensure_ascii=False), flush=True)
    if execution is not None:
        execution.doCleanups()


if __name__ == "__main__":
    main()

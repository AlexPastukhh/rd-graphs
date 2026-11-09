#!/usr/bin/env python3
"""Disposable real Helper/Viewer fixture. Enrollment controls are stdio-only."""
import argparse
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import socket
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    return SourceFileLoader(name, str(ROOT / path)).load_module()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-fixture", action="store_true", required=True)
    parser.parse_args()
    tests = load("viewer_execution_fixture", "tests/rdg-approval-execution.test.py")
    helper = load("viewer_helper_fixture", "tools/rdg-workflow-helper.py")
    authn = load("viewer_webauthn_fixture", "tools/rdg-webauthn.py")
    surface_module = load("viewer_surface_fixture", "tools/rdg-approval-surface.py")
    fx = tests.ApprovalExecution("test_exact_signed_execution_separates_three_actors_without_granting_ai")
    fx.setUp()
    configured, requests, counter = {}, {}, 0
    principal = "synthetic-operator"
    mode = {"drop": False, "crash": False}

    def factory(origin):
        verifier = authn.Verifier("localhost", origin)
        executor = fx.bridge(fx.human, verifier=verifier)
        original = executor.complete
        def complete(ceremony, response):
            def fail(stage):
                if mode["crash"] and stage == "prepared":
                    mode["crash"] = False
                    raise ValueError("SYNTHETIC_AFTER_ACCEPTANCE")
            return original(ceremony, response, failpoint=fail)
        executor.complete = complete
        surface = surface_module.ApprovalSurface(executor)
        configured.update(verifier=verifier, executor=executor, surface=surface)
        return surface

    editor = helper.PortableEditor(fx.config(), fx.token)
    server = helper.make_server(editor, approval_factory=factory)
    bare = helper.make_server(editor)
    original_output = server.RequestHandlerClass.output
    def output(handler, status, body, content_type="application/json"):
        if mode["drop"] and isinstance(body, dict) and body.get("accepted") is True:
            mode["drop"] = False
            try:
                handler.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            handler.connection.close()
            return
        return original_output(handler, status, body, content_type)
    server.RequestHandlerClass.output = output
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (server, bare)]
    for thread in threads:
        thread.start()
    fields = {"ready": set(), "register_begin": set(), "register_complete": {"ceremonyId", "response"},
              "setup": {"scenario"}, "inspect": {"requestId"}, "add_plan": {"requestId"},
              "revoke_executor": set(), "change_target": {"requestId"}}
    try:
        for line in sys.stdin:
            request = None
            try:
                request = json.loads(line)
                method, body = request["method"], request.get("body", {})
                if method not in fields or set(body) != fields[method]:
                    raise ValueError("SYNTHETIC_MESSAGE_FIELDS")
                if method == "ready":
                    result = {"url": server.session_url, "bareUrl": bare.session_url,
                              "realHumanProof": False, "syntheticOwnersOnly": True}
                elif method == "register_begin":
                    result = configured["verifier"].begin_registration(principal, "Synthetic Viewer operator")
                elif method == "register_complete":
                    result = configured["verifier"].complete_registration(body["ceremonyId"], body["response"])
                elif method == "setup":
                    scenario = body["scenario"]
                    if scenario not in ("edit", "reject", "replace", "crash", "drop", "revoked", "stale"):
                        raise ValueError("SYNTHETIC_SCENARIO")
                    counter += 1
                    target = fx.create("viewer-" + scenario + "-" + str(counter))
                    if scenario == "replace":
                        source = fx.create("paper-" + str(counter), "ready")
                        p1 = fx.create("P1-" + str(counter))
                        fx.app().request(fx.placement(p1, target))
                        command = fx.replace_request(target, source)
                    else:
                        if scenario != "stale":
                            lock = fx.app().schema("lock_set", target)["request"]
                            lock.update(operation="edit", principals=["key:synthetic-human"],
                                authorityPrincipal="user:fixture-setup", message="Synthetic protected title",
                                note="Synthetic setup")
                            tests.BASE.CLI.application(fx.config(), fx.token, attribution="user").request(lock)
                        command = fx.edit(target, "Подтверждённое название " + str(counter))
                    mode["crash"], mode["drop"] = scenario == "crash", scenario == "drop"
                    pending = fx.app().approval_request(command,
                        "Изменить тестовые данные по этому запросу. <img src=x onerror=alert(1)>")
                    requests[command["transactionId"]] = command
                    result = {"requestId": command["transactionId"], "targetPackageId": target,
                              "desiredTitle": command.get("data", {}).get("changes", {}).get("title"),
                              "state": pending["state"]}
                elif method == "inspect":
                    command = requests[body["requestId"]]
                    state = fx.app().approval_read(body["requestId"])
                    current = fx.current(command["targetPackageId"])
                    result = {"state": state["state"], "graph": current["graph"],
                              "plan": current["plan"], "receipt": fx.app().receipt(
                                  command["targetPackageId"], command["transactionId"])}
                elif method == "add_plan":
                    command = requests[body["requestId"]]
                    owner = fx.create("P2-" + str(counter))
                    fx.app().request(fx.placement(owner, command["targetPackageId"]))
                    result = {"packageId": owner}
                elif method == "change_target":
                    command = requests[body["requestId"]]
                    fx.command(command["targetPackageId"], "edit", nodeId="R1",
                               changes={"description": "Concurrent legitimate synthetic edit"})
                    result = {"changed": True}
                else:
                    fx.authority.manage("revoke", fx.admin, {"id": fx.human_grant})
                    result = {"revoked": True}
                reply = {"id": request["id"], "ok": True, "result": result}
            except (ValueError, TypeError, KeyError, OSError) as exc:
                reply = {"id": request.get("id") if isinstance(request, dict) else None,
                         "ok": False, "error": str(exc)}
            print(json.dumps(reply, ensure_ascii=False), flush=True)
    finally:
        for item in (server, bare):
            item.shutdown()
            item.server_close()
        for thread in threads:
            thread.join(timeout=3)
        fx.doCleanups()


if __name__ == "__main__":
    main()

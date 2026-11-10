#!/usr/bin/env python3
"""Synthetic owner manager for real process-restart and revocation tests."""
import argparse
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
def load(name, file):
    return SourceFileLoader(name, str(ROOT / file)).load_module()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-fixture", action="store_true", required=True)
    parser.parse_args()
    tests = load("persistent_manager_fixture", "tests/rdg-approval-execution.test.py")
    module = load("persistent_manager_store", "tools/rdg-credential-store.py")
    fx = tests.ApprovalExecution("test_exact_signed_execution_separates_three_actors_without_granting_ai")
    fx.setUp()
    store = module.CredentialStore(fx.authority)
    with socket.socket() as selected:
        selected.bind(("127.0.0.1", 0))
        port = selected.getsockname()[1]
    principal = "synthetic-persistent-operator"
    spec = {"principalId": principal, "displayName": "Тестовая постоянная учётная запись",
        "namespaceId": fx.namespace, "executorGrantId": fx.human_grant,
        "authorityPrincipal": "key:synthetic-human", "rpId": "localhost",
        "origin": "http://localhost:" + str(port), "active": True}
    store.configure_binding(fx.admin, spec, expected_revision=0)
    initial_grants = fx.authority._read()["grants"]
    initial_grant_revision = fx.authority._read()["revision"]
    runtime = {"process": None, "ready": None, "errors": [], "stderr": "", "serial": 0}
    control_queue, ready = queue.Queue(), threading.Event()
    requests, counter = {}, 0
    secret_config = fx.base / "synthetic-runtime.json"

    def stop():
        process = runtime["process"]
        if process is not None and process.poll() is None:
            process.stdin.write(json.dumps({"method": "shutdown"}) + "\n")
            process.stdin.flush()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=5)
        runtime["process"] = None

    def start(permit=None):
        ready.clear()
        config = {"application": fx.config(), "executorToken": fx.human_token,
            "initiatorToken": fx.token, "executorGrantId": fx.human_grant,
            "principalId": principal, "authorityPrincipal": "key:synthetic-human",
            "enrollmentPermit": permit}
        fd = os.open(secret_config, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as output:
            json.dump(config, output)
        env = {k: v for k, v in os.environ.items() if not k.startswith("RDG_AUTH_")}
        process = subprocess.Popen([sys.executable, "-B", "-u",
            str(ROOT / "tests/rdg-persistent-viewer-runtime.py"), "--synthetic-fixture",
            "--config", str(secret_config), "--port", str(port)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env)
        runtime["process"] = process
        def read_errors():
            runtime["stderr"] += process.stderr.read()
        def read_output():
            for line in process.stdout:
                value = json.loads(line)
                if value.get("event") == "ready":
                    runtime["ready"] = value
                    ready.set()
                elif value.get("event") == "staged":
                    try:
                        ident = runtime["revokeId"]
                        row = next(r for r in store.inspect(fx.admin)["credentials"]
                                   if r["credentialId"] == ident)
                        store.revoke_credential(fx.admin, ident, expected_revision=row["revision"])
                    except Exception as exc:
                        runtime["errors"].append(str(exc))
                    finally:
                        process.stdin.write(json.dumps({"method": "continue"}) + "\n")
                        process.stdin.flush()
                else:
                    control_queue.put(value)
        threading.Thread(target=read_errors, daemon=True).start()
        threading.Thread(target=read_output, daemon=True).start()
        if not ready.wait(20):
            raise ValueError("SYNTHETIC_RUNTIME_START_FAILED: " + runtime["stderr"][-2000:])

    def arm(credential_id):
        runtime["revokeId"] = credential_id
        runtime["serial"] += 1
        runtime["process"].stdin.write(json.dumps({"id": runtime["serial"], "method": "arm"}) + "\n")
        runtime["process"].stdin.flush()
        reply = control_queue.get(timeout=10)
        if reply.get("id") != runtime["serial"] or not reply.get("ok"):
            raise ValueError("SYNTHETIC_CONTROL_FAILED")

    try:
        start(store.issue_enrollment(fx.admin, principal))
        fields = {"ready": set(), "setup": set(), "inspect": {"requestId"},
                  "restart": set(), "arm_revoke": {"credentialId"}, "audit": {"proofSHA256"},
                  "reinvite": set(), "ordinary_invite": set(), "state": set()}
        for line in sys.stdin:
            request = None
            try:
                request = json.loads(line)
                method, body = request["method"], request.get("body", {})
                if method not in fields or set(body) != fields[method]:
                    raise ValueError("SYNTHETIC_MESSAGE_FIELDS")
                if method == "ready":
                    result = runtime["ready"]
                elif method == "setup":
                    counter += 1
                    target = fx.create("persistent-viewer-" + str(counter))
                    lock = fx.app().schema("lock_set", target)["request"]
                    lock.update(operation="edit", principals=["key:synthetic-human"],
                        authorityPrincipal="user:fixture-setup", message="Synthetic persistent lock",
                        note="Synthetic setup")
                    tests.BASE.CLI.application(fx.config(), fx.token, attribution="user").request(lock)
                    command = fx.edit(target, "После перезапуска " + str(counter))
                    fx.app().approval_request(command, "Проверка сохранённого ключа и точной операции")
                    requests[command["transactionId"]] = command
                    result = {"requestId": command["transactionId"], "packageId": target,
                              "title": command["data"]["changes"]["title"]}
                elif method == "inspect":
                    command = requests.get(body["requestId"]) or fx.app().approval_read(body["requestId"])["request"]
                    current = fx.current(command["targetPackageId"])
                    result = {"graph": current["graph"],
                        "receipt": fx.app().receipt(command["targetPackageId"], command["transactionId"]),
                        "state": fx.app().approval_read(command["transactionId"])["state"]}
                elif method in ("restart", "reinvite"):
                    stop()
                    start(store.issue_enrollment(fx.admin, principal) if method == "reinvite" else None)
                    result = runtime["ready"]
                elif method == "arm_revoke":
                    arm(body["credentialId"])
                    result = {"armed": True}
                elif method == "audit":
                    result = store.audit_proof(fx.admin, body["proofSHA256"])
                elif method == "ordinary_invite":
                    store.issue_enrollment(fx.token, principal)
                    raise ValueError("SYNTHETIC_AGENT_WAS_ALLOWED")
                else:
                    result = store.inspect(fx.admin)
                    result.update(grantsUnchanged=fx.authority._read()["grants"] == initial_grants,
                        grantRevisionUnchanged=fx.authority._read()["revision"] == initial_grant_revision,
                        fixtureErrors=runtime["errors"], packageCount=len(fx.app().catalog()["packages"]),
                        ownerTokenInRuntimeConfig=fx.admin in secret_config.read_text(),
                        realHumanProof=False, osIsolationVerified=False)
                reply = {"id": request["id"], "ok": True, "result": result}
            except Exception as exc:
                reply = {"id": request.get("id") if isinstance(request, dict) else None,
                         "ok": False, "error": str(exc)}
            print(json.dumps(reply, ensure_ascii=False), flush=True)
    finally:
        stop()
        fx.doCleanups()


if __name__ == "__main__":
    main()

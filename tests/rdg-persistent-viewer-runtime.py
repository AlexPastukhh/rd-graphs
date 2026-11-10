#!/usr/bin/env python3
"""Synthetic persistent Viewer child. Control pipe is not a product endpoint."""
import argparse
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
def load(name, file):
    return SourceFileLoader(name, str(ROOT / file)).load_module()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-fixture", action="store_true", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    helper = load("persistent_child_helper", "tools/rdg-workflow-helper.py")
    cli = load("persistent_child_cli", "tools/rdg-portable.py")
    authn = load("persistent_child_authn", "tools/rdg-webauthn.py")
    credentials = load("persistent_child_credentials", "tools/rdg-credential-store.py")
    executor_module = load("persistent_child_executor", "tools/rdg-approval-executor.py")
    surface_module = load("persistent_child_surface", "tools/rdg-approval-surface.py")
    output_lock, proceed = threading.Lock(), threading.Event()
    mode = {"armed": False}
    def emit(value):
        with output_lock:
            print(json.dumps(value), flush=True)
    def factory(origin):
        app = cli.application(config["application"], config["executorToken"])
        store = credentials.CredentialStore(app.authority)
        verifier = authn.Verifier("localhost", origin, credential_store=store)
        executor = executor_module.ApprovalExecutor(app, verifier, config["principalId"],
            config["authorityPrincipal"], config["executorGrantId"])
        original = executor.complete
        def complete(ceremony, response):
            def failpoint(stage):
                if mode["armed"] and stage == "staged":
                    mode["armed"] = False
                    proceed.clear()
                    emit({"event": "staged"})
                    if not proceed.wait(10):
                        raise ValueError("SYNTHETIC_OWNER_REVOKE_TIMEOUT")
            return original(ceremony, response, failpoint=failpoint)
        executor.complete = complete
        return surface_module.ApprovalSurface(executor, enrollment_permit=config.get("enrollmentPermit"))
    editor = helper.PortableEditor(config["application"], config["initiatorToken"])
    server = helper.make_server(editor, approval_factory=factory, listen_port=args.port)
    def control():
        for line in sys.stdin:
            command = json.loads(line)
            if command["method"] == "shutdown":
                server.shutdown()
                return
            if command["method"] == "continue":
                proceed.set()
            elif command["method"] == "arm":
                mode["armed"] = True
                emit({"id": command["id"], "ok": True})
    threading.Thread(target=control, daemon=True).start()
    emit({"event": "ready", "url": server.session_url, "processId": os.getpid()})
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

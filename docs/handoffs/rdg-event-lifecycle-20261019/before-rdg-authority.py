#!/usr/bin/env python3
"""Opt-in RDG bearer grants. Not a proof of human identity or an OS sandbox."""
import argparse
import fcntl
import hashlib
import hmac
import json
import os
import secrets
import tempfile
from contextlib import contextmanager
from pathlib import Path

def require(condition, code):
    if not condition:
        raise ValueError("AUTH_" + code)

def token_digest(value):
    require(isinstance(value, str) and len(value) >= 32, "TOKEN_REQUIRED")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def new_token():
    return "rdg_" + secrets.token_urlsafe(40)

def valid_scope(value):
    return (isinstance(value, str) and
            ((value.startswith("workspaces/") and (value.endswith("/") or value.endswith("/graph.json"))) or
             (value.startswith("plans/") and (value.endswith("/") or value.endswith("/plan.json")))) and
            ".." not in value and "\\" not in value and "//" not in value)

def covers(scope, target):
    return target.startswith(scope) if scope.endswith("/") else scope == target

def validate_spec(spec):
    require(isinstance(spec, dict) and set(spec) <= {"label","permissions","scopes"},
            "SPEC_INVALID")
    permissions, scopes = spec.get("permissions"), spec.get("scopes")
    require(isinstance(permissions, list) and permissions and
            len(permissions) == len(set(permissions)) and
            all(isinstance(p, str) and (p == "grant.admin" or p == "graph.write" or
            p.startswith(("graph.", "plan.")) and p.replace(".","").replace("_","").isalnum())
            for p in permissions), "PERMISSIONS_INVALID")
    require(isinstance(scopes, list) and scopes and len(scopes) == len(set(scopes)) and
            all(valid_scope(s) for s in scopes), "SCOPES_INVALID")
    require(isinstance(spec.get("label",""), str) and len(spec.get("label","")) <= 120,
            "LABEL_INVALID")
    return {"label":spec.get("label",""), "permissions":permissions, "scopes":scopes}

def subset(spec, actor):
    return (all(p in actor["permissions"] or
                (p.startswith("graph.") and "graph.write" in actor["permissions"])
                for p in spec["permissions"]) and
            all(any(covers(a, b) for a in actor["scopes"]) for b in spec["scopes"]))

class Authority:
    def __init__(self, path):
        self.path = Path(path)

    def _read(self):
        require(self.path.is_file() and not self.path.is_symlink(), "STORE_UNAVAILABLE")
        data = json.loads(self.path.read_text(encoding="utf-8"))
        require(data.get("version") == 1 and isinstance(data.get("grants"), dict),
                "STORE_INVALID")
        return data

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".auth-")
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump(data, out, ensure_ascii=False, sort_keys=True, indent=2)
                out.write("\n")
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp, self.path)
            fd_dir = os.open(self.path.parent, os.O_DIRECTORY)
            try:
                os.fsync(fd_dir)
            finally:
                os.close(fd_dir)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def _actor(self, data, token):
        digest = token_digest(token)
        for ident, grant in data["grants"].items():
            if hmac.compare_digest(grant["digest"], digest):
                require(grant["active"], "TOKEN_REVOKED")
                return ident, grant
        raise ValueError("AUTH_TOKEN_UNKNOWN")

    def init_local(self, plan_capable=False, applicability_capable=False):
        """Local operator bootstrap only; not a browser/Helper user identity proof."""
        require(not applicability_capable or plan_capable, "PLAN_CAPABILITY_REQUIRED")
        require(not self.path.exists(), "ALREADY_INITIALIZED")
        token = new_token()
        root = {"digest":token_digest(token), "label":"local-owner",
                "permissions":["grant.admin","graph.write"], "scopes":["workspaces/"],
                "active":True, "owner":True}
        if plan_capable:
            root["permissions"] += ["plan.create", "plan.edit", "plan.branch", "plan.read",
                                    "plan.accept", "plan.event_attest"]
            root["scopes"].append("plans/")
        if applicability_capable:
            root["permissions"].append("plan.applicability.write")
        self._save({"version":1, "revision":1, "grants":{"root":root}})
        return {"id":"root", "token":token, "bootstrap":"LOCAL_ONLY"}

    def manage(self, operation, token, request=None):
        request = request or {}
        lockpath = self.path.with_suffix(self.path.suffix + ".lock")
        lockpath.parent.mkdir(parents=True, exist_ok=True)
        with lockpath.open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            data = self._read()
            _, admin = self._actor(data, token)
            require("grant.admin" in admin["permissions"], "ADMIN_REQUIRED")
            if operation == "list":
                return {"revision":data["revision"], "grants":[
                    {"id":i, **{k:v for k,v in g.items() if k != "digest"}}
                    for i,g in data["grants"].items()
                    if admin.get("owner") or subset(g, admin)]}
            if operation == "issue":
                spec = validate_spec(request)
                require(subset(spec, admin), "DELEGATION_CEILING")
                ident, secret = "g_" + secrets.token_hex(10), new_token()
                data["grants"][ident] = {**spec, "digest":token_digest(secret),
                                         "active":True,"owner":False}
                response = {"id":ident,"token":secret}
            else:
                ident = request.get("id")
                require(isinstance(ident, str) and ident in data["grants"],
                        "GRANT_UNKNOWN")
                target = data["grants"][ident]
                require(not target["owner"], "OWNER_IMMUTABLE")
                require(admin.get("owner") or subset(target, admin),
                        "TARGET_OUTSIDE_DELEGATION")
                if operation == "amend":
                    spec = validate_spec(request.get("grant"))
                    require(subset(spec, admin), "DELEGATION_CEILING")
                    target.update(spec)
                elif operation == "revoke":
                    target["active"] = False
                else:
                    raise ValueError("AUTH_UNKNOWN_OPERATION")
                response = {"id":ident,"active":target["active"]}
            data["revision"] += 1
            self._save(data)
            return response

    def authorize_package(self, token, package):
        data = self._read()
        ident, grant = self._actor(data, token)
        for change in package.get("changes", []):
            file = change.get("file")
            require(isinstance(file, str) and
                    any(covers(s, file) for s in grant["scopes"]),
                    "SCOPE_DENIED: file=" + str(file) + "; request graph scope from user in Helper")
            ops = ["graph.create"] if "create" in change else []
            if "create" in change:
                graph = change["create"]
                require(isinstance(graph, dict), "INVALID_CREATE")
                require(not graph.get("events") and graph.get("selected") is not True,
                        "CREATE_CANDIDATES_ONLY: file=" + file)
                for node in graph.get("nodes", []):
                    require(isinstance(node, dict), "INVALID_CREATE_NODE")
                    require(node.get("kind") != "decision" and not (
                        node.get("kind") == "action" and node.get("status") != "candidate"),
                        "CREATE_CANDIDATES_ONLY: file=" + file)
            for item in (change.get("patch") or {}).get("operations", []):
                name = item.get("op")
                require(isinstance(name, str), "OPERATION_UNNAMED")
                # Only dedicated choice operations may change a decision.
                # Generic add/update/event functions cannot smuggle acceptance.
                if name == "add_node":
                    node = item.get("node")
                    require(isinstance(node, dict) and
                            node.get("kind") != "decision" and not (
                                node.get("kind") == "action" and
                                node.get("status") != "candidate"),
                            "CANDIDATE_MUTATION_ONLY: file=" + file)
                elif name == "update_node":
                    changes = item.get("changes")
                    require(isinstance(changes, dict) and
                            changes.get("status") not in (
                                "committed", "selected", "superseded"),
                            "ACCEPTANCE_REQUIRES_DEDICATED_OPERATION: file=" + file)
                elif name == "append_event":
                    event = item.get("event")
                    require(isinstance(event, dict) and event.get("type") not in (
                        "decision_selected", "decision_revised",
                        "action_selected", "action_reconsidered"),
                        "SELECTION_EVENT_REQUIRES_DEDICATED_OPERATION: file=" + file)
                elif name in ("select_option", "revise_decision"):
                    event = item.get("event")
                    require(isinstance(event, dict) and event.get("by") != "user",
                            "BEARER_CANNOT_CLAIM_USER_IDENTITY")
                if name == "graph_edit":
                    name += "." + str(item.get("action"))
                ops.append("graph." + name)
            if change.get("metadata") is not None:
                ops.append("graph.metadata")
            require(ops, "EMPTY_CHANGE")
            for permission in ops:
                require("graph.write" in grant["permissions"] or
                        permission in grant["permissions"],
                        "MISSING_PERMISSION: " + permission +
                        "; file=" + file + "; request via Helper")
        return {"grantId":ident,"grantRevision":data["revision"]}

    def authorize_plan(self, token, permissions, target):
        data = self._read()
        ident, grant = self._actor(data, token)
        require(isinstance(target, str) and target.startswith("plans/") and
                valid_scope(target) and any(covers(s, target) for s in grant["scopes"]),
                "PLAN_SCOPE_DENIED")
        for permission in permissions:
            # graph.write and grant.admin never imply Plan write/accept/attest.
            require(permission.startswith("plan.") and permission in grant["permissions"],
                    "MISSING_PERMISSION: " + permission)
        return {"grantId":ident, "grantRevision":data["revision"]}

    def authorize_snapshot_read(self, token, plan_target, graph_targets):
        data = self._read()
        ident, grant = self._actor(data, token)
        targets = [("plan.read", plan_target)] + [("graph.read", t) for t in graph_targets]
        for permission, target in targets:
            prefix = "plans/" if permission == "plan.read" else "workspaces/"
            require(isinstance(target, str) and target.startswith(prefix) and
                    valid_scope(target) and any(covers(s, target) for s in grant["scopes"]),
                    "SNAPSHOT_READ_SCOPE_DENIED")
            require(permission in grant["permissions"], "MISSING_PERMISSION: " + permission)
        return {"grantId": ident, "grantRevision": data["revision"]}

    @contextmanager
    def checked_plan_transaction(self, token, permissions, target):
        lockpath = self.path.with_suffix(self.path.suffix + ".lock")
        lockpath.parent.mkdir(parents=True, exist_ok=True)
        with lockpath.open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield self.authorize_plan(token, permissions, target)

    @contextmanager
    def checked_transaction(self, token, package):
        """Serialize revocation with the durable transaction acceptance point.

        Lock order: writer lock, then grants lock. A prepared journal is a
        durable acceptance; subsequent recovery must finish it, even if revoked.
        """
        lockpath = self.path.with_suffix(self.path.suffix + ".lock")
        lockpath.parent.mkdir(parents=True, exist_ok=True)
        with lockpath.open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield self.authorize_package(token, package)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["init","issue","amend","revoke","list"])
    parser.add_argument("--store",default=os.environ.get("RDG_AUTH_STORE"))
    parser.add_argument("--plan-capable", action="store_true", help="Opt-in local bootstrap only; does not upgrade existing stores")
    parser.add_argument("--applicability-capable", action="store_true", help="Explicitly opt in a new local Plan store to applicability writes")
    options = parser.parse_args()
    require(options.store, "STORE_PATH_REQUIRED")
    auth = Authority(options.store)
    request = json.load(__import__("sys").stdin) if options.command in (
        "issue","amend","revoke") else None
    result = auth.init_local(plan_capable=options.plan_capable, applicability_capable=options.applicability_capable) if options.command == "init" else auth.manage(
        options.command, os.environ.get("RDG_AUTH_TOKEN"), request)
    print(json.dumps(result,ensure_ascii=False))

if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        import sys
        print("ERROR: " + str(exc),file=sys.stderr)
        sys.exit(1)

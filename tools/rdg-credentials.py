#!/usr/bin/env python3
"""Owner-only opt-in WebAuthn administration. No grants or OS ACLs are changed."""
import argparse
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "configure", "invite", "revoke", "audit"))
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--expected-revision", type=int)
    parser.add_argument("--principal")
    parser.add_argument("--proof-sha")
    parser.add_argument("--credential-id")
    parser.add_argument("--permit-file", type=Path)
    args = parser.parse_args()
    if os.name != "posix":
        raise ValueError("RDG_CREDENTIAL_OPERATOR_POSIX_RUNTIME_REQUIRED")
    authority = SourceFileLoader("credential_operator_authority",
        str(ROOT / "tools/rdg-authority.py")).load_module().Authority(args.store)
    module = SourceFileLoader("credential_operator_store",
        str(ROOT / "tools/rdg-credential-store.py")).load_module()
    store = module.CredentialStore(authority)
    token = os.environ.get("RDG_AUTH_TOKEN")
    if args.command == "inspect":
        result = store.inspect(token)
    elif args.command == "audit":
        if not args.proof_sha:
            raise ValueError("RDG_CREDENTIAL_PROOF_SHA_REQUIRED")
        result = store.audit_proof(token, args.proof_sha)
    elif args.command == "configure":
        if args.expected_revision is None:
            raise ValueError("RDG_CREDENTIAL_EXPECTED_REVISION_REQUIRED")
        result = store.configure_binding(token, json.load(sys.stdin),
                                         expected_revision=args.expected_revision)
    elif args.command == "revoke":
        if args.expected_revision is None or not args.credential_id:
            raise ValueError("RDG_CREDENTIAL_REVOKE_FIELDS")
        result = store.revoke_credential(token, args.credential_id,
                                         expected_revision=args.expected_revision)
    else:
        path = args.permit_file
        if not args.principal or path is None or not path.is_absolute() or not path.parent.is_dir():
            raise ValueError("RDG_CREDENTIAL_PRIVATE_PERMIT_FILE_REQUIRED")
        if path.resolve().is_relative_to(ROOT) or any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError("RDG_CREDENTIAL_PERMIT_PATH")
        # Authenticate before creating even an empty capability file.
        store.inspect(token)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            permit = store.issue_enrollment(token, args.principal)
            output.write(permit + "\n")
            output.flush()
            os.fsync(output.fileno())
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        result = {"issued": True, "principalId": args.principal,
                  "permitFile": str(path), "rawPermitReturned": False}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)

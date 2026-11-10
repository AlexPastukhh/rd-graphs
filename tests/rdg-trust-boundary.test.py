#!/usr/bin/env python3
"""Pilot trust-boundary probe: manual attribution is not human identity proof."""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIX = SourceFileLoader("trust_fixture", str(ROOT / "tests/rdg-portable-store.test.py")).load_module()
CLI = SourceFileLoader("trust_cli", str(ROOT / "tools/rdg-portable.py")).load_module()


class TrustBoundary(unittest.TestCase):
    setUp = FIX.PortableStore.setUp

    def config(self):
        return {
            "packageRoot": str(self.root),
            "namespaceId": self.namespace,
            "coordinationRoot": str(self.base),
            "authorityStore": str(self.authority.path),
        }

    def req(self, op, **fields):
        import uuid
        return {"transactionId": str(uuid.uuid4()), "op": op, **fields}

    def test_manual_user_attribution_has_explicit_unproven_receipt(self):
        app = CLI.application(self.config(), self.token, attribution="user")
        request = self.req("create", path="working/trust", role="working", title="Trust")
        result = app.request(request)
        ident = result["packages"][0]["packageId"]
        current = app.read(ident, True)
        edit = self.req("core", targetPackageId=ident,
            expectedPackageRevision=current["package"]["revision"],
            expectedGraphRevision=current["graph"]["revision"],
            command="edit", data={"nodeId": "R1", "changes": {"title": "Edited"}},
            note="Synthetic manual-session probe")
        app.request(edit)
        event = app.read(ident, True)["graph"]["events"][-1]
        self.assertEqual(event["by"], "user")
        self.assertEqual(event["verifiedTrustReceipt"]["mode"], "local-manual-session")
        self.assertNotIn("humanPrincipal", event)
        self.assertNotIn("humanBearer", event)


if __name__ == "__main__":
    unittest.main()

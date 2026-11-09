#!/usr/bin/env python3
"""Operation-based lock semantics on isolated core fixtures."""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
M = SourceFileLoader("lock_model", str(ROOT / "tools/rdg-core-model.py")).load_module()


class Locks(unittest.TestCase):
    def setUp(self):
        self.g = M.blank("locks", "Locks", "lock-space", "R0", "Root", "Synthetic")
        self.seq = 0

    def do(self, command, by="assistant", principal=None, coordinated=False, **data):
        self.seq += 1
        event = {"id": "EV-" + str(self.seq), "by": by,
                 "note": "Lock fixture: " + command,
                 "verifiedTrustReceipt": {"mode": "test-only"}}
        if principal is not None:
            event["authorityPrincipal"] = principal
        self.g, _ = M.apply(self.g, {
            "schemaVersion": 1, "expectedRevision": self.g["revision"],
            "operations": [{"op": "graph_edit", "action": "core_" + command,
                            "data": data, "event": event}],
        }, True, coordinated=coordinated)
        return self.g["events"][-1]

    def test_hard_lock_is_pair_scoped_and_warning_only_informs(self):
        self.do("lock_set", by="user", principal="user:owner",
                nodeId="R0", operation="edit", mode="hard",
                principals=["key:k1", "key:k2"], message="R0 edit is protected")
        with self.assertRaisesRegex(ValueError, "OBJECT_OPERATION_LOCK_REQUIRED"):
            self.do("edit", nodeId="R0", changes={"title": "Denied"})
        with self.assertRaisesRegex(ValueError, "OBJECT_OPERATION_LOCK_REQUIRED"):
            self.do("edit", by="user", principal="user:owner",
                    nodeId="R0", changes={"title": "Text user is not key"})
        event = self.do("edit", principal="key:k2", nodeId="R0",
                        changes={"title": "Allowed with second key"})
        self.assertEqual(event["type"], "core_entity_changed")

        self.do("add", entity={"id": "R1", "kind": "requirement",
                               "title": "Child", "description": "Child",
                               "scope": "Synthetic"})
        self.do("lock_set", by="user", principal="user:owner",
                nodeId="R1", operation="edit", mode="warning",
                principals=[], message="Review before editing child")
        event = self.do("edit", nodeId="R1",
                        changes={"title": "Child changed"})
        self.assertEqual(event["lockWarnings"][0]["operation"], "edit")

    def test_no_child_inheritance_and_lock_removal_requires_owner_path(self):
        self.do("add", entity={"id": "R1", "kind": "requirement",
                               "title": "Child", "description": "Child",
                               "scope": "Synthetic"})
        self.do("lock_set", by="user", principal="user:owner",
                nodeId="R0", operation="edit", mode="hard",
                principals=["key:parent"], message="Parent edit protected")
        event = self.do("edit", nodeId="R1",
                        changes={"title": "Independent child edit"})
        self.assertEqual(event["type"], "core_entity_changed")
        with self.assertRaisesRegex(ValueError, "LOCK_USER_PATH_REQUIRED"):
            self.do("lock_remove", nodeId="R0", operation="edit",
                    disposition="Remove")
        self.do("lock_remove", by="user", principal="key:parent",
                nodeId="R0", operation="edit", disposition="Owner removal")
        self.assertNotIn("locks", M.entities(self.g)["R0"])


    def test_link_checks_link_lock_on_endpoints_and_reports_warning(self):
        self.do("add", entity={"id": "R1", "kind": "requirement", "title": "Child",
                               "description": "Child", "scope": "Synthetic"})
        self.do("lock_set", by="user", principal="user:owner", nodeId="R0",
                operation="link", mode="hard", principals=["key:links"], message="Protect links")
        self.do("lock_set", by="user", principal="user:owner", nodeId="R1",
                operation="link", mode="warning", principals=[], message="Inspect link")
        edge = {"id": "D1", "type": "DERIVES", "from": "R0", "to": "R1"}
        with self.assertRaisesRegex(ValueError, "OBJECT_OPERATION_LOCK_REQUIRED"):
            self.do("link", edge=edge)
        event = self.do("link", principal="key:links", edge=edge)
        self.assertEqual(event["lockWarnings"][0]["operation"], "link")
        self.assertEqual(event["lockWarnings"][0]["nodeId"], "R1")

    def test_remove_checks_the_removed_object_operation(self):
        self.do("add", entity={"id": "R1", "kind": "requirement", "title": "Child",
                               "description": "Child", "scope": "Synthetic"})
        self.do("lock_set", by="user", principal="user:owner", nodeId="R1",
                operation="remove", mode="hard", principals=["key:remove"], message="Protect removal")
        with self.assertRaisesRegex(ValueError, "OBJECT_OPERATION_LOCK_REQUIRED"):
            self.do("remove", nodeIds=["R1"], coordinated=True)
        self.do("remove", principal="key:remove", nodeIds=["R1"], coordinated=True)
        self.assertNotIn("R1", M.entities(self.g))

    def test_edit_lock_does_not_implicitly_lock_link_or_remove(self):
        self.do("add", entity={"id": "R1", "kind": "requirement", "title": "Child",
                               "description": "Child", "scope": "Synthetic"})
        for nid in ("R0", "R1"):
            self.do("lock_set", by="user", principal="user:owner", nodeId=nid,
                    operation="edit", mode="hard", principals=["key:edit"], message="Only definition")
        self.do("link", edge={"id": "D1", "type": "DERIVES", "from": "R0", "to": "R1"})
        self.do("remove", nodeIds=["R1"], coordinated=True)
        self.assertIn("R0", M.entities(self.g))


if __name__ == "__main__":
    unittest.main()

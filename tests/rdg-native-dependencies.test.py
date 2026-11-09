#!/usr/bin/env python3
"""Native L1/L2 semantic impact contract on isolated core fixtures."""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import copy
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
M = SourceFileLoader("native_dependency_model", str(ROOT / "tools/rdg-core-model.py")).load_module()


class NativeDependencies(unittest.TestCase):
    def setUp(self):
        self.g = M.blank("native", "Native", "native-space", "R0", "Root", "Synthetic")
        self.seq = 0

    def do(self, command, **data):
        self.seq += 1
        event = {
            "id": "EV-" + str(self.seq), "by": "assistant",
            "note": "Native dependency fixture: " + command,
            "verifiedTrustReceipt": {"mode": "test-only"},
        }
        if "evidenceRefs" in data:
            event["evidenceRefs"] = data.pop("evidenceRefs")
        self.g, _ = M.apply(self.g, {
            "schemaVersion": 1, "expectedRevision": self.g["revision"],
            "operations": [{"op": "graph_edit", "action": "core_" + command,
                            "data": data, "event": event}],
        }, True)
        return self.g["events"][-1]

    def add(self, ident, kind="requirement", **extra):
        entity = {"id": ident, "kind": kind, "title": ident, **extra}
        if kind == "requirement":
            entity.update(description=extra.get("description", ident),
                          scope="Synthetic scope")
        self.do("add", entity=entity)

    def edge(self, typ, source, target, **extra):
        self.do("link", edge={"id": "E-" + str(self.seq + 1),
                              "type": typ, "from": source, "to": target, **extra})

    def native(self, source, dependent, level):
        self.do("dependency_add", edge={
            "id": "N-" + str(self.seq + 1), "type": "DEPENDS_ON",
            "from": source, "to": dependent, "dependencyLevel": level})

    def clear_all_reviews(self):
        ids = [i for i, node in M.entities(self.g).items()
               if node.get("review", {}).get("required")]
        if ids:
            observed = {i: rev for j in ids for i, rev in M.pins(self.g, j).items()}
            self.do("review", nodeIds=ids, observed=observed)

    def test_l1_and_l2_have_distinct_direct_scope(self):
        self.add("R1"); self.add("R2"); self.add("R3")
        self.add("Y1"); self.add("Y2")
        self.edge("DERIVES", "R1", "R2")
        self.native("R1", "Y1", "L1")
        self.native("R1", "Y2", "L2")
        self.clear_all_reviews()
        self.clear_all_reviews()

        self.do("edit", nodeId="R1", changes={"title": "R1 renamed"})
        self.assertTrue(M.entities(self.g)["Y1"]["review"]["required"])
        self.assertTrue(M.entities(self.g)["Y2"]["review"]["required"])
        self.clear_all_reviews()

        self.do("edit", nodeId="R2", changes={"title": "Direct child changed"})
        self.assertFalse(M.entities(self.g)["Y1"]["review"]["required"])
        self.assertTrue(M.entities(self.g)["Y2"]["review"]["required"])
        self.clear_all_reviews()

        self.edge("DERIVES", "R1", "R3")
        self.assertFalse(M.entities(self.g)["Y1"]["review"]["required"])
        self.assertTrue(M.entities(self.g)["Y2"]["review"]["required"])
        self.clear_all_reviews()
        self.do("edit", nodeId="R3", changes={"title": "New direct child changed"})
        self.assertFalse(M.entities(self.g)["Y1"]["review"]["required"])
        self.assertTrue(M.entities(self.g)["Y2"]["review"]["required"])
        self.clear_all_reviews()
        impact = M.dependency_impacts(self.g, self.g, {"R1"})
        self.assertFalse(impact)  # same snapshot has no semantic delta
        self.clear_all_reviews()

        self.edge("DERIVES", "R2", "R3")
        self.assertFalse(M.entities(self.g)["Y1"]["review"]["required"])
        self.assertFalse(M.entities(self.g)["Y2"]["review"]["required"])

    def test_requirement_l2_tracks_direct_drives_definition_and_relation(self):
        self.add("A1", "action"); self.add("Y")
        self.edge("DRIVES", "R0", "A1")
        self.native("R0", "Y", "L2")
        self.clear_all_reviews(); self.clear_all_reviews()
        self.do("edit", nodeId="A1", changes={"title": "Driver changed"})
        self.assertTrue(M.entities(self.g)["Y"]["review"]["required"])
        self.clear_all_reviews()
        self.add("A2", "action")
        self.edge("DRIVES", "R0", "A2")
        self.assertTrue(M.entities(self.g)["Y"]["review"]["required"])

    def test_lost_child_result_is_not_parent_definition_staleness(self):
        self.add("R2"); self.add("Y")
        self.edge("DERIVES", "R0", "R2")
        self.native("R0", "Y", "L2")
        self.clear_all_reviews(); self.clear_all_reviews()
        self.do("falsify", nodeId="R2", evidenceRefs=[{"path":"evidence/r2","sha256":"0"*64}])
        # Core completion review may reopen the parent obligation; native L2(R0)
        # must not treat the child's lost result as a semantic definition hit.
        self.assertTrue(M.entities(self.g)["R0"]["review"]["required"])
        self.assertFalse(M.entities(self.g)["Y"]["review"]["required"])

    def test_action_l2_includes_direct_output_canon_and_context_only(self):
        self.add("Rout"); self.add("Rnested")
        self.add("A1", "action")
        self.add("C1", "context", description="Initial context")
        self.add("K1", "canon", evaluationMode="comment-only-v1",
                  comment="Initial comment", arguments=[])
        self.add("Y", "requirement")
        self.edge("DRIVES", "R0", "A1")
        self.edge("INTRODUCES", "A1", "Rout",
                  origin={"role": "method_correctness"})
        self.edge("DERIVES", "Rout", "Rnested")
        self.edge("CONTEXT_FOR", "C1", "A1")
        self.edge("CANON_FOR", "K1", "A1")
        self.native("A1", "Y", "L2")
        self.clear_all_reviews()
        self.clear_all_reviews()

        self.do("edit", nodeId="A1", changes={"title": "Action changed"})
        self.assertTrue(M.entities(self.g)["Y"]["review"]["required"])
        self.clear_all_reviews()
        self.do("edit", nodeId="R0", changes={"title": "Driver requirement changed"})
        self.assertTrue(M.entities(self.g)["Y"]["review"]["required"])
        self.clear_all_reviews()

        self.do("edit", nodeId="Rout", changes={"title": "Output changed"})
        self.assertTrue(M.entities(self.g)["Y"]["review"]["required"])
        self.clear_all_reviews()
        self.do("edit", nodeId="Rnested", changes={"title": "Nested changed"})
        self.assertFalse(M.entities(self.g)["Y"]["review"]["required"])
        self.do("edit", nodeId="K1", changes={"comment": "Comment changed"})
        self.assertTrue(M.entities(self.g)["Y"]["review"]["required"])
        self.clear_all_reviews()
        self.do("edit", nodeId="C1", changes={"title": "Context changed"})
        self.assertTrue(M.entities(self.g)["Y"]["review"]["required"])
        causes = M.entities(self.g)["Y"]["review"]["causes"]
        self.assertTrue(any(c.get("nativeImpact") for c in causes))


    def test_s28_shared_canon_criterion_is_not_recursive_action_l2(self):
        # Reuse the actual seven shared info identities and 35 INFO_FOR links
        # from the five-Canon checkpoint fixture. This is a synthetic copy.
        self.g = json.loads((ROOT / "tools/rdg-agent-lenses/checkpoint.json").read_text())
        M.validate(self.g)
        self.assertEqual(len([e for e in self.g["edges"] if e["type"] == "INFO_FOR"]), 35)
        self.assertEqual(len([e for e in self.g["edges"]
                              if e["type"] == "INFO_FOR" and e["from"] == "CP-C3"]), 5)
        self.add("S28-Y")
        self.native("CP-A1", "S28-Y", "L2")
        self.clear_all_reviews()

        self.do("edit", nodeId="CP-C3",
                changes={"title": "Shared C3 updated across five own Canon views"})
        self.assertFalse(M.entities(self.g)["S28-Y"].get("review", {}).get("required", False))
        for i in range(1, 6):
            view = M.focused_view(self.g, "CANON-CP-A" + str(i))
            c3 = next(item for item in view["entities"] if item["id"] == "CP-C3")
            self.assertEqual(c3["title"], "Shared C3 updated across five own Canon views")

        self.do("edit", nodeId="CANON-CP-A1",
                changes={"comment": "Direct comment on the subscribed Action's Canon"})
        self.assertTrue(M.entities(self.g)["S28-Y"]["review"]["required"])
        self.assertTrue(any(impact["sourceId"] == "CP-A1" and impact["level"] == "L2"
                            and "direct-relations" in impact["changedParts"]
                            for cause in M.entities(self.g)["S28-Y"]["review"]["causes"]
                            for impact in cause.get("nativeImpact", [])))
        self.clear_all_reviews()

        self.do("edit", nodeId="CANON-CP-A2",
                changes={"comment": "A different Canon's own comment"})
        self.assertFalse(M.entities(self.g)["S28-Y"]["review"]["required"])

        # A separately declared native dependency on the shared C3 is now
        # allowed; explanatory INFO_FOR links remain non-dependencies.
        self.native("CP-C3", "S28-Y", "L1")
        self.assertTrue(M.entities(self.g)["S28-Y"]["review"]["required"])
        self.clear_all_reviews()
        self.do("edit", nodeId="CP-C3",
                changes={"title": "C3 native dependency changed"})
        self.assertTrue(M.entities(self.g)["S28-Y"]["review"]["required"])
        self.clear_all_reviews()

        self.add("S28-Z")
        before = copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError, "INFO_DEPENDENCY_LEVEL_REQUIRED"):
            self.edge("DEPENDS_ON", "CP-C3", "S28-Z")
        self.assertEqual(self.g, before)

    def test_output_origin_change_is_an_l2_provenance_hit(self):
        self.add("Rout"); self.add("A1", "action"); self.add("Y")
        self.edge("DRIVES", "R0", "A1")
        output_id="E-"+str(self.seq+1)
        self.edge("INTRODUCES", "A1", "Rout",
                  origin={"role": "method_correctness"})
        self.native("Rout", "Y", "L2")
        self.clear_all_reviews(); self.clear_all_reviews()
        self.do("output_origin", edgeId=output_id,
                origin={"role": "subgoal", "requirementIds": ["R0"]})
        self.assertTrue(M.entities(self.g)["Y"]["review"]["required"])
        causes=M.entities(self.g)["Y"]["review"]["causes"]
        self.assertTrue(any("direct-relations" in impact["changedParts"]
                            for cause in causes for impact in cause.get("nativeImpact", [])))

    def test_parent_provenance_is_direct_and_ignores_unrelated_overlays(self):
        self.add("R1"); self.add("R2"); self.add("Y")
        self.add("I", "info", description="Unrelated visible information")
        self.edge("DERIVES", "R0", "R1")
        parent_edge = next(e["id"] for e in self.g["edges"] if e["type"] == "DERIVES")
        self.native("R1", "Y", "L2")
        self.clear_all_reviews(); self.clear_all_reviews()

        self.edge("INFO_FOR", "I", "R1")
        self.assertFalse(M.entities(self.g)["Y"]["review"]["required"])
        self.edge("DERIVES", "R0", "R2")
        self.assertFalse(M.entities(self.g)["Y"]["review"]["required"])
        self.clear_all_reviews()

        self.do("unlink", edgeId=parent_edge, disposition="Parent provenance changed")
        self.assertTrue(M.entities(self.g)["Y"]["review"]["required"])
        causes = M.entities(self.g)["Y"]["review"]["causes"]
        self.assertTrue(any("direct-relations" in impact["changedParts"]
                            for cause in causes for impact in cause.get("nativeImpact", [])))
        self.clear_all_reviews()
        self.edge("DERIVES", "R2", "R1")
        self.assertTrue(M.entities(self.g)["Y"]["review"]["required"])

    def test_cosmetic_edit_is_audited_and_exempts_only_native_definition_impacts(self):
        self.add("R1"); self.add("X"); self.add("Y"); self.add("Z"); self.add("Legacy")
        self.edge("DERIVES", "R0", "R1")
        self.native("R1", "X", "L1")
        self.native("R1", "Y", "L2")
        self.native("R0", "Z", "L2")
        self.edge("DEPENDS_ON", "R1", "Legacy")
        self.clear_all_reviews(); self.clear_all_reviews()
        previous = M.entities(self.g)["R1"]["title"]

        event = self.do("edit", nodeId="R1", changes={"title": "R1 typography"}, cosmetic=True)
        self.assertIs(event["cosmetic"], True)
        self.assertEqual(event["before"]["R1"]["title"], previous)
        self.assertEqual(event["after"]["R1"]["title"], "R1 typography")
        for ident in ("X", "Y", "Z"):
            self.assertFalse(M.entities(self.g)[ident]["review"]["required"], ident)
        self.assertTrue(M.entities(self.g)["Legacy"]["review"]["required"])
        self.assertTrue(M.entities(self.g)["R1"]["review"]["required"])
        self.clear_all_reviews()

        event = self.do("edit", nodeId="R1", changes={"title": "R1 substantive"}, cosmetic=False)
        self.assertIs(event["cosmetic"], False)
        for ident in ("X", "Y", "Z"):
            self.assertTrue(M.entities(self.g)[ident]["review"]["required"], ident)

    def test_cosmetic_exception_cannot_hide_structural_changes_or_leak_to_next_edit(self):
        self.add("R1"); self.add("R2"); self.add("X"); self.add("Y")
        self.edge("DERIVES", "R1", "R2")
        self.native("R1", "X", "L1"); self.native("R1", "Y", "L2")
        self.clear_all_reviews(); self.clear_all_reviews()
        self.do("edit", nodeId="R1", changes={"title": "Typography"}, cosmetic=True)
        self.assertFalse(M.entities(self.g)["Y"]["review"]["required"])
        self.edge("DERIVES", "R1", "R0")
        self.assertTrue(M.entities(self.g)["Y"]["review"]["required"])
        self.assertFalse(M.entities(self.g)["X"]["review"]["required"])
        self.clear_all_reviews()
        event = self.do("edit", nodeId="R1", changes={"title": "Normal rename"})
        self.assertNotIn("cosmetic", event)
        self.assertTrue(M.entities(self.g)["X"]["review"]["required"])

    def test_cosmetic_marker_requires_a_boolean_and_is_writer_owned_in_history(self):
        import copy
        before = copy.deepcopy(self.g)
        for value in ("true", 1, None, {}, []):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "COSMETIC"):
                self.do("edit", nodeId="R0", changes={"title": "Invalid marker"}, cosmetic=value)
            self.assertEqual(self.g, before)
        with self.assertRaisesRegex(ValueError, "WRITER_EVENT_FIELDS"):
            M.apply(self.g, {"schemaVersion": 1, "expectedRevision": self.g["revision"],
                "operations": [{"op": "graph_edit", "action": "core_edit",
                    "data": {"nodeId": "R0", "changes": {"title": "Forged audit"}},
                    "event": {"id": "FORGED", "by": "assistant", "note": "Invalid cosmetic audit",
                              "verifiedTrustReceipt": {"mode": "test-only"}, "cosmetic": True}}]}, True)
        self.assertEqual(self.g, before)


if __name__ == "__main__":
    unittest.main()

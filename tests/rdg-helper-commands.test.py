"""RDG-owned, offline, grouped general chat command catalog contract."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "kit/helper-commands/build.py"
spec = importlib.util.spec_from_file_location("rdg_helper_commands", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class HelperCommandsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_source, self.old_output, self.old_legacy, self.old_lenses = (
            module.SOURCE, module.OUTPUT, module.LEGACY_OUTPUT, module.LENSES)
        self.addCleanup(self.restore)
        self.source = Path(self.tmp.name) / "commands.json"
        module.SOURCE = self.source
        module.OUTPUT = Path(self.tmp.name) / "catalog-v2.json"
        module.LEGACY_OUTPUT = Path(self.tmp.name) / "catalog.json"
        module.LENSES = ROOT / "tools/rdg-agent-lenses/catalog.json"
        self.original = json.loads(self.old_source.read_text())
        self.write_source(self.original)

    def restore(self):
        module.SOURCE, module.OUTPUT, module.LEGACY_OUTPUT, module.LENSES = (
            self.old_source, self.old_output, self.old_legacy, self.old_lenses)

    def write_source(self, data):
        self.source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_complete_catalog_is_deterministic_and_does_not_require_lens_markdown(self):
        first = module.validate()
        self.assertEqual(module.encode(first), module.encode(module.validate()))
        self.assertEqual(first["schemaVersion"], 2)
        self.assertEqual(first["kind"], "rdg-chat-commands")
        self.assertTrue(first["complete"])
        self.assertEqual([g["id"] for g in first["groups"]], ["start", "lenses"])
        self.assertEqual(len(first["commands"]), 22)
        self.assertEqual(first["commands"], sorted(first["commands"], key=lambda c: c["id"]))
        lens = [c for c in first["commands"] if c["kind"] == "lens-launcher"]
        self.assertEqual(len(lens), 21)
        self.assertEqual({c["lensRefs"][0]["lensKey"] for c in lens}, module.lens_keys())
        self.assertIn("rdg.lens.operate", [c["id"] for c in lens])
        self.assertIn("rdg.lens.develop", [c["id"] for c in lens])
        self.assertEqual(set(lens[0]), {
            "id", "kind", "title", "description", "groupId", "lensRefs", "insertText"})
        self.assertNotIn("sourcePath", str(first))

    def test_bootstrap_is_multi_lens_workflow_with_additional_instructions(self):
        catalog = module.validate()
        boot = next(c for c in catalog["commands"] if c["id"] == "rdg.command.bootstrap")
        self.assertEqual(boot["kind"], "workflow")
        self.assertEqual(boot["groupId"], "start")
        self.assertEqual([r["lensKey"] for r in boot["lensRefs"]], ["orient", "work"])
        self.assertIn("первом входе", boot["insertText"])
        self.assertIn("НЕ является поручением создавать", boot["insertText"])
        for key in ("orient", "work"):
            self.assertIn("rdg-agent.py lens --lens " + key, boot["insertText"])
        self.assertNotIn("Bearer ", boot["insertText"])

    def test_author_owned_text_and_group_title_remain_exact(self):
        data = copy.deepcopy(self.original)
        data["commands"][0]["insertText"] += "\nДополнительная инструкция RDG."
        data["groups"][0]["title"] = "Старт RDG"
        self.write_source(data)
        actual = module.validate()
        changed = next(c for c in actual["commands"] if c["id"] == data["commands"][0]["id"])
        self.assertEqual(changed["insertText"], data["commands"][0]["insertText"])
        self.assertEqual(actual["groups"][0]["title"], "Старт RDG")

    def test_duplicate_and_missing_lens_launchers_fail_closed(self):
        data = copy.deepcopy(self.original)
        data["commands"].append(copy.deepcopy(data["commands"][0]))
        self.write_source(data)
        with self.assertRaisesRegex(ValueError, "RDG_COMMAND_ID"):
            module.validate()
        data = copy.deepcopy(self.original)
        data["commands"] = [c for c in data["commands"] if c["id"] != "rdg.lens.orient"]
        self.write_source(data)
        with self.assertRaisesRegex(ValueError, "RDG_COMMAND_COVERAGE"):
            module.validate()

    def test_bad_identity_profile_secret_and_missing_invocation_fail_closed(self):
        for mutation, marker in [
            (lambda c: c["lensRefs"][0].update(modelProfile="rdg-core-v1"), "RDG_COMMAND_PROFILE"),
            (lambda c: c["lensRefs"][0].update(lensKey="not-existing"), "RDG_COMMAND_UNKNOWN_LENS"),
            (lambda c: c.update(insertText="Bearer " + "a" * 40), "RDG_COMMAND_TEXT"),
            (lambda c: c.update(insertText="other content"), "RDG_COMMAND_BAD_INVOCATION"),
        ]:
            with self.subTest(marker=marker):
                data = copy.deepcopy(self.original)
                mutation(data["commands"][0])
                self.write_source(data)
                with self.assertRaisesRegex(ValueError, marker):
                    module.validate()

    def test_invalid_group_reference_and_duplicate_group_fail_closed(self):
        data = copy.deepcopy(self.original)
        data["commands"][0]["groupId"] = "missing"
        self.write_source(data)
        with self.assertRaisesRegex(ValueError, "RDG_COMMAND_UNKNOWN_GROUP"):
            module.validate()
        data = copy.deepcopy(self.original)
        data["groups"].append(copy.deepcopy(data["groups"][0]))
        self.write_source(data)
        with self.assertRaisesRegex(ValueError, "RDG_COMMAND_GROUP_ID"):
            module.validate()

    def test_instruction_without_lenses_and_multi_lens_workflow_allowed(self):
        data = copy.deepcopy(self.original)
        data["commands"].append({
            "id": "rdg.command.readme", "kind": "instruction",
            "title": "Инструкция", "description": "Без конкретной линзы",
            "groupId": "start", "lensRefs": [],
            "insertText": "Прочитай текущие доступные инструкции и сообщи результат без записи."
        })
        data["commands"].append({
            "id": "rdg.command.composite", "kind": "workflow",
            "title": "Комбинация", "description": "Адресное чтение нескольких линз",
            "groupId": "start", "lensRefs": [
                {"role": "lens", "lensKey": key, "modelProfile": "rdg-decision-v1"}
                for key in ("checkpoint", "research")
            ],
            "insertText": "read rdg-agent.py lens --lens checkpoint; read rdg-agent.py lens --lens research"
        })
        self.write_source(data)
        catalog = module.validate()
        self.assertEqual(len(catalog["commands"]), 24)
        data["commands"][-1]["lensRefs"].append(data["commands"][-1]["lensRefs"][0])
        self.write_source(data)
        with self.assertRaisesRegex(ValueError, "RDG_COMMAND_DUPLICATE_LENS"):
            module.validate()

    def test_existing_published_catalog_matches_compiled_source(self):
        self.assertEqual(module.encode(module.validate()), self.old_output.read_bytes())
        legacy = module.legacy_projection(module.validate())
        self.assertEqual(len(legacy["commands"]), 21)
        self.assertEqual(module.encode(legacy), self.old_legacy.read_bytes())
        # A V2 release must not silently mutate the existing V1 file.
        self.assertEqual(self.old_legacy.read_bytes(),
                         (ROOT / "kit/helper-commands/catalog.json").read_bytes())


if __name__ == "__main__":
    unittest.main()

"""RDG-owned, offline bulk chat launcher commands contract."""
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
        self.old_source, self.old_output, self.old_lenses = module.SOURCE, module.OUTPUT, module.LENSES
        self.addCleanup(self.restore)
        self.source = Path(self.tmp.name) / "commands.json"
        module.SOURCE = self.source
        module.OUTPUT = Path(self.tmp.name) / "catalog.json"
        module.LENSES = ROOT / "tools/rdg-agent-lenses/catalog.json"
        self.original = json.loads(self.old_source.read_text())
        self.write_source(self.original)

    def restore(self):
        module.SOURCE, module.OUTPUT, module.LENSES = (
            self.old_source, self.old_output, self.old_lenses)

    def write_source(self, data):
        self.source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_full_catalog_is_deterministic_and_makes_no_markdown_requirement(self):
        first = module.validate()
        second = module.validate()
        self.assertEqual(module.encode(first), module.encode(second))
        self.assertEqual(len(first["commands"]), 21)
        self.assertTrue(first["complete"])
        self.assertEqual(first["kind"], "rdg-chat-launcher-commands")
        self.assertEqual(first["commands"], sorted(first["commands"], key=lambda x: x["id"]))
        self.assertEqual({c["lensRef"]["lensKey"] for c in first["commands"]},
                         module.lens_keys())
        self.assertIn("rdg.lens.operate", [c["id"] for c in first["commands"]])
        self.assertIn("rdg.lens.develop", [c["id"] for c in first["commands"]])
        self.assertEqual(set(first["commands"][0]), {"id","kind","title","description","lensRef","insertText"})
        self.assertNotIn("sourcePath", str(first))

    def test_command_text_is_author_owned_not_regenerated(self):
        data = copy.deepcopy(self.original)
        data["commands"][0]["insertText"] += "\nДополнительная RDG-инструкция владельца."
        self.write_source(data)
        actual = module.validate()
        changed = next(c for c in actual["commands"] if c["id"] == data["commands"][0]["id"])
        self.assertEqual(changed["insertText"], data["commands"][0]["insertText"])

    def test_duplicate_and_missing_commands_fail_closed(self):
        data = copy.deepcopy(self.original)
        data["commands"].append(data["commands"][0])
        self.write_source(data)
        with self.assertRaisesRegex(ValueError, "RDG_COMMAND_ID"):
            module.validate()
        data = copy.deepcopy(self.original)
        data["commands"].pop()
        self.write_source(data)
        with self.assertRaisesRegex(ValueError, "RDG_COMMAND_COVERAGE"):
            module.validate()

    def test_wrong_model_unknown_lens_and_secret_fail_closed(self):
        for mutation, marker in [
            (lambda c:c["lensRef"].update(modelProfile="rdg-core-v1"), "RDG_COMMAND_PROFILE"),
            (lambda c:c["lensRef"].update(lensKey="not-existing"), "RDG_COMMAND_UNKNOWN_LENS"),
            (lambda c:c.update(insertText="Bearer " + "a"*40), "RDG_COMMAND_TEXT"),
            (lambda c:c.update(insertText="other content"), "RDG_COMMAND_BAD_INVOCATION"),
        ]:
            with self.subTest(marker=marker):
                data = copy.deepcopy(self.original)
                mutation(data["commands"][0])
                self.write_source(data)
                with self.assertRaisesRegex(ValueError, marker):
                    module.validate()

    def test_existing_catalog_matches_compiled_source(self):
        self.assertEqual(module.encode(module.validate()),
                         self.old_output.read_bytes())


if __name__ == "__main__":
    unittest.main()

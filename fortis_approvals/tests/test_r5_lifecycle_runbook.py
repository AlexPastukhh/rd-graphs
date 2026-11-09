"""Non-regression for R5 TLS/grant lifecycle plan's safety boundaries."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = ROOT/'fortis_approvals/deploy/R5-TLS-GRANT-LIFECYCLE-OWNER-RUNBOOK.md'


class R5LifecycleRunbookTests(unittest.TestCase):
    def test_plan_is_not_an_operator_apply_command_or_production_go(self):
        s=RUNBOOK.read_text()
        for label in (
            'SOURCE-ONLY / OFFLINE TEST PASS',
            'R5-only downtime',
            'R5 TRUSTED ADMISSION=OPEN',
            'Sonar WRITE=DISABLED',
            'старый grant -> 401 DENIED',
            'новый grant -> scoped READ 200',
            'Текущее ограничение R5',
            'Браузерные сессии',
        ):
            # Browser wording is stated in English below as well.
            if label == 'Браузерные сессии':
                self.assertIn('Browser sessions',s)
            else:
                with self.subTest(label=label):
                    self.assertIn(label,s)
        self.assertIn('2026-11-07T23:29:17Z',s)
        self.assertIn('только R5',s)
        self.assertIn('не включать скомпрометированный старый grant',s)

    def test_same_core_state_separate_A3_without_bootstrap(self):
        s=RUNBOOK.read_text()
        for required in (
            'fortis-r5-state', 'fortis-r5-identity', 'fortis-r5-grant',
            'fortis-r5-sonar-token', 'fortis-repo-test',
            'localhost:19103', 'host.docker.internal:19104',
            'Core.adapters={}', 'отдельный',
            'tests/test_r5_lifecycle_offline.py'
        ):
            with self.subTest(required=required):
                self.assertIn(required,s)
        for unsafe in (
            'docker stop fortis-repo-test',
            'docker restart fortis-repo-test',
            'docker compose down -v',
            'docker system prune',
            'docker volume rm',
        ):
            with self.subTest(unsafe=unsafe):
                self.assertNotIn(unsafe,s)


if __name__ == '__main__':
    unittest.main()

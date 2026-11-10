"""Static checks for the exact-ID, no-network owner R7 P1 image audit."""
import re
from pathlib import Path
from zipfile import ZipFile
import unittest

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT/'fortis_approvals/deploy/Audit-R7-P1-Windows-ImageOffline-20261102.ps1'
ZIP = Path('/workspace/repo/Workfiles/fortis-r7-unified-source-review-p1-20261102.zip')
IMAGE_ID = 'sha256:2c634df43b988d05a83a5479aaf1d51fbea863da9a4e602aae7ce938815e4b78'

class AuditScriptStaticTests(unittest.TestCase):
    def test_exact_pinned_tag_and_all_19_installed_file_hashes(self):
        text = AUDIT.read_text(encoding='utf-8')
        self.assertIn(IMAGE_ID, text)
        self.assertIn('review-p1-20261102-7755e84e', text)
        pairs = dict(re.findall(r"'(/opt/[^']+)' = '([0-9a-f]{64})'", text))
        self.assertEqual(len(pairs), 19)
        with ZipFile(ZIP) as z:
            manifest = {name: sha for sha, name in (
                line.split('  ', 1) for line in
                z.read('SOURCE-MANIFEST.sha256').decode('ascii').splitlines())}
        for installed, sha in pairs.items():
            source = ('fortis_approvals/requirements-owner.txt'
                      if installed == '/opt/requirements-owner.txt'
                      else installed.removeprefix('/opt/fortis/'))
            self.assertEqual(sha, manifest[source], installed)
        self.assertEqual(set(manifest)-set(
            'fortis_approvals/requirements-owner.txt' if name == '/opt/requirements-owner.txt'
            else name.removeprefix('/opt/fortis/') for name in pairs),
            {'fortis_approvals/deploy/Dockerfile-R7-Unified-Read-Ask-Candidate'})

    def test_two_disposable_isolated_runs_no_deploy_or_pip_repeat(self):
        text = AUDIT.read_text(encoding='utf-8')
        self.assertEqual(text.count('& docker run @common'), 2)
        for flag in ('--rm', '--pull=never', '--network', "'none'", '--read-only',
                     '--user', '--cap-drop', 'no-new-privileges:true'):
            self.assertIn(flag, text)
        self.assertIn('preflight-imports', text)
        self.assertIn('FORTIS_R7_UNIFIED_READ_ASK_IMPORTS_PASS', text)
        self.assertIn('FORTIS_R7_SONAR_POST=DISABLED', text)
        self.assertIn("--format '{{json .Config}}' $image", text)
        self.assertNotIn('$imageTag', text)
        for forbidden in ('& docker build', '& docker start', '& docker stop',
                          '& docker restart', '& docker compose', '& docker exec',
                          '& docker volume', '& docker rm', '-m pip check', '-m pip list',
                          'SONAR_TOKEN='):
            self.assertNotIn(forbidden.lower(), text.lower(), forbidden)

if __name__ == '__main__':
    unittest.main()

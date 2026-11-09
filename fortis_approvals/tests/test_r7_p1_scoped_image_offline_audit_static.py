"""Static source/allowlist validation for owner-only scoped R7 image audit.

No Windows Docker commands are run by these tests.
"""
from hashlib import sha256
from pathlib import Path
import re
import unittest
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'fortis_approvals/deploy/Audit-R7-P1-Scoped-Windows-ImageOffline-20261102.ps1'
PACKAGE=Path('/workspace/repo/Workfiles/fortis-r7-unified-source-review-p1-scoped-20261102.zip')
IMAGE='sha256:23667619c6dfac33466d0e0b4b60bcb22fb7dccb14b0a024f2c062bac0a18ce4'
SCRIPT_SHA='84c469e780f19544cacbc350450e503b6c73bfa03b5159e251805193ec5c17c2'


class ScopedP1ImageAuditStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=SCRIPT.read_bytes()
        cls.source=cls.data.decode('utf-8')

    def test_exact_owner_image_and_new_standalone_audit(self):
        self.assertEqual(sha256(self.data).hexdigest(),SCRIPT_SHA)
        self.assertIn(IMAGE,self.source)
        self.assertIn('review-p1-scoped-20261102-fac3131e',self.source)
        self.assertIn("$containerPrefix = 'fortis-r7-p1-scoped-audit-20261102-'",self.source)
        self.assertIn('$id -cne $expectedId',self.source)
        self.assertNotIn('review-p1-20261102-7755e84e',self.source)
        self.assertNotIn('sha256:2c634df',self.source)
        self.assertIn('FORTIS_R7_P1_SCOPED_IMAGE_OFFLINE_IMPORT_AND_SOURCE_AUDIT_PASS',self.source)

    def test_all_installed_sources_match_new_sealed_manifest(self):
        expected=dict(re.findall(r"'(/opt/[^']+)' = '([0-9a-f]{64})'",self.source))
        self.assertEqual(len(expected),19)
        with ZipFile(PACKAGE) as archive:
            manifest=dict((name,digest) for digest,name in (
                line.split('  ',1) for line in archive.read('SOURCE-MANIFEST.sha256').decode('ascii').splitlines()))
        missing=set(manifest)
        for installed,digest in expected.items():
            name=('fortis_approvals/requirements-owner.txt'
                  if installed=='/opt/requirements-owner.txt'
                  else installed.removeprefix('/opt/fortis/'))
            self.assertIn(name,manifest)
            self.assertEqual(digest,manifest[name])
            missing.remove(name)
        self.assertEqual(missing,{'fortis_approvals/deploy/Dockerfile-R7-Unified-Read-Ask-Candidate'})
        for important in ('sonar_read.py','r7_unified_candidate.py','r7_unified_server.py'):
            self.assertIn(important,self.source)

    def test_two_isolated_no_network_disposable_containers_no_mutation(self):
        script=self.source
        self.assertEqual(script.count('& docker run @common'),2)
        for required in ('--rm','--pull=never','--network','--read-only',
                         "'none'",'--cap-drop','no-new-privileges:true',
                         'preflight-imports','FORTIS_R7_UNIFIED_READ_ASK_IMPORTS_PASS',
                         'FORTIS_R7_SONAR_POST=DISABLED',
                         'FORTIS_R7_P1_SCOPED_AUDIT_DISPOSABLE_CONTAINERS_REMOVED_PASS',
                         'FORTIS_R7_P1_SCOPED_PINNED_PIP_AND_PIP_CHECK=NOT_REPEATED'):
            self.assertIn(required,script)
        for forbidden in ('& docker build','& docker start','& docker stop',
                          '& docker restart','& docker compose','& docker volume',
                          '& docker exec','& docker cp','& docker rm',
                          '-m pip check','-m pip list','SONAR_TOKEN='):
            self.assertNotIn(forbidden.lower(),script.lower())
        self.assertNotIn('$imageTag',script)
        self.assertIn("docker image inspect --format '{{json .Config}}' $image",script)

if __name__=='__main__':
    unittest.main()

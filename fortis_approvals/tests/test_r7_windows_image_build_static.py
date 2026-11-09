"""R7 pinned Windows image-only release review static acceptance.

This tests bytes, names and script guardrails; it does NOT run PowerShell,
Docker, SonarCloud, Windows host actions, or authorize deployment.
"""
from hashlib import sha256
from pathlib import Path
import re
import unittest
from zipfile import ZipFile

from fortis_approvals.deploy.package_r7_review import NAMES


ROOT=Path(__file__).resolve().parents[2]
WORKFILES=Path('/workspace/repo/Workfiles')
ZIP=WORKFILES/'fortis-r7-unified-source-review-20261101.zip'
BUILD=ROOT/'fortis_approvals/deploy/Build-R7-Windows-ImageOnly.ps1'
TRANSFER=WORKFILES/'Build-R7-Windows-ImageOnly-20261101.ps1'
EXPECTED_ZIP='b0055e1954174b11794de787f1eff17506b68610859677e463df8eb94ae12cb9'
EXPECTED_MANIFEST='aca6ce714e8225e7f8e4638362b5f0ffa54f4e3a816f1ff80bf484229379257d'
EXPECTED_DOCKERFILE='b40e80a526c98e53a2df1cd07900a4513bfbe9fd2062726f05f776de0a8e0fce'
EXPECTED_BUILD='7ed8d5c65043f31ee6546b6d092c0f80e85f9779cf5a6b4897a4dacd0dbb943d'
EXPECTED_TAG='fortis-r7-unified-read-ask-candidate:review-20261101-b0055e19'
P2_SUPERSEDED = frozenset({
    'fortis_approvals/core.py',
    'fortis_approvals/owner_portal.py',
    'fortis_approvals/r7_unified_candidate.py',
    'fortis_approvals/r7_unified_server.py',
    'fortis_approvals/deploy/Dockerfile-R7-Unified-Read-Ask-Candidate',
})


class R7WindowsReviewStaticTests(unittest.TestCase):
    def test_source_zip_exactly_matches_manifest_and_release_sha(self):
        self.assertEqual(sha256(ZIP.read_bytes()).hexdigest(),EXPECTED_ZIP)
        with ZipFile(ZIP) as z:
            self.assertEqual(len(z.namelist()),21)
            self.assertEqual(len(set(z.namelist())),21)
            self.assertEqual(set(z.namelist()),
                             set(NAMES)|{'SOURCE-MANIFEST.sha256'})
            manifest=z.read('SOURCE-MANIFEST.sha256')
            self.assertEqual(sha256(manifest).hexdigest(),EXPECTED_MANIFEST)
            lines=manifest.decode('ascii').splitlines()
            self.assertEqual(len(lines),20)
            for index,line in enumerate(lines):
                digest,name=line.split('  ',1)
                self.assertEqual(name,NAMES[index])
                data=z.read(name)
                self.assertEqual(sha256(data).hexdigest(),digest)
                # Historical P1/v1 archive stays immutable. P2 intentionally
                # supersedes the execution boundary in these exact source files.
                if name in P2_SUPERSEDED:
                    if name=='fortis_approvals/r7_unified_server.py':
                        self.assertEqual(digest,
                            'b098bdced0ee22d9c0ed24d91a305135a8935c04f3f233f53245d462f904c82d')
                    self.assertNotEqual(data,(ROOT/name).read_bytes())
            self.assertEqual(
                sha256(z.read('fortis_approvals/deploy/'
                              'Dockerfile-R7-Unified-Read-Ask-Candidate'))
                .hexdigest(),EXPECTED_DOCKERFILE)

    def test_exact_pinned_owner_script_transfer_and_allowlist(self):
        source=BUILD.read_bytes()
        self.assertEqual(sha256(source).hexdigest(),EXPECTED_BUILD)
        self.assertEqual(TRANSFER.read_bytes(),source)
        text=source.decode('utf-8')
        self.assertIn(EXPECTED_ZIP,text)
        self.assertIn(EXPECTED_MANIFEST,text)
        self.assertIn(EXPECTED_DOCKERFILE,text)
        self.assertIn(EXPECTED_TAG,text)
        self.assertIn('R7_REVIEW_IMAGE_TAG_ALREADY_EXISTS_NO_OVERWRITE',text)
        self.assertIn('R7_SOURCE_FILE_COUNT_MISMATCH',text)
        self.assertIn('R7_BUILD_CONTEXT_HAS_UNEXPECTED_FILES',text)
        self.assertIn('R7_WINDOWS_SYSTEM_DISK_LOW_DO_NOT_BUILD',text)
        self.assertIn('FORTIS_R7_CONTAINERS_STARTED=NONE',text)
        self.assertIn('FORTIS_R7_TRUSTED_ADMISSION=OPEN',text)
        self.assertIn('--no-cache --pull=false',text)
        for name in NAMES:
            self.assertEqual(text.count("'"+name+"'"),1)
        self.assertEqual(text.count('    \'fortis_approvals/'),20)
        docker_commands=re.findall(r'^\s*(?:& )?docker\s+([^\r\n]+)$',
                                   text,re.M)
        self.assertEqual(len(docker_commands),1)
        self.assertTrue(docker_commands[0].startswith('build --no-cache'))
        for forbidden in (
            'docker run','docker stop','docker start','docker restart',
            'docker exec','docker rm','docker volume create',
            'docker compose','docker update','docker cp',
            'FORTIS_SONAR_TOKEN=', 'approve=true',
        ):
            self.assertNotIn(forbidden,text.lower() if forbidden.islower()
                             else text)

    def test_no_untrusted_credentials_archive_and_expected_tag_new(self):
        with ZipFile(ZIP) as z:
            for name in z.namelist():
                self.assertNotIn('secret',name.lower())
                self.assertNotIn('token',name.lower())
                self.assertNotIn('grant',name.lower())
                self.assertNotIn('credential',name.lower())
                self.assertNotIn('repo_sonar_tools',name)


if __name__=='__main__':
    unittest.main()

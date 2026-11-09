"""Pinned R7 v2 owner source review: exact isolated ZIP import regression.

Tests v2 as a *minimal Docker COPY archive*, not the developer checkout.
Never runs Docker, touches Windows, provisions tokens, or modifies v1 artifacts.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from fortis_approvals.deploy.package_r7_review import NAMES


ROOT=Path(__file__).resolve().parents[2]
WORKFILES=Path('/workspace/repo/Workfiles')
V2=WORKFILES/'fortis-r7-unified-source-review-v2-20261101.zip'
V1=WORKFILES/'fortis-r7-unified-source-review-20261101.zip'
SOURCE=ROOT/'fortis_approvals/deploy/Build-R7-Windows-ImageOnly-v2.ps1'
TRANSFER=WORKFILES/'Build-R7-Windows-ImageOnly-v2-20261101.ps1'
EXPECTED_V2_ZIP='f9791fd1e5cee092092897825e7886fe040cc0d71d5ea43179c5593cb5ac9df7'
EXPECTED_V2_MANIFEST='c59e2b02f0404dab835c094806f5cb634e84ed81cb69f9c88d9004591db2a995'
EXPECTED_V2_BUILD='60fcfdb9eab1a101e887343a62fcf9e92f41d8f1cef10798db52f3c4d54d6971'
EXPECTED_TAG='fortis-r7-unified-read-ask-candidate:review-20261101-f9791fd1'
EXPECTED_IMPORT=('FORTIS_R7_UNIFIED_READ_ASK_IMPORTS_PASS\n'
                 'FORTIS_R7_SONAR_POST=DISABLED\n')
P2_SUPERSEDED = frozenset({
    'fortis_approvals/core.py',
    'fortis_approvals/owner_portal.py',
    'fortis_approvals/r7_unified_candidate.py',
    'fortis_approvals/r7_unified_server.py',
    'fortis_approvals/deploy/Dockerfile-R7-Unified-Read-Ask-Candidate',
})


def isolated_import(zip_path):
    with TemporaryDirectory(prefix='r7-package-exact-test-') as tmp:
        with ZipFile(zip_path) as z:
            z.extractall(tmp)
        # Child Python may see ONLY the archive sources, not checkout source.
        env = dict(os.environ)
        env['PYTHONPATH']=tmp
        env['PYTHONNOUSERSITE']='1'
        env['PYTHONDONTWRITEBYTECODE']='1'
        run=subprocess.run(
            [sys.executable,'-B','-m',
             'fortis_approvals.r7_unified_server','preflight-imports'],
            cwd=tmp,env=env,timeout=12,capture_output=True,text=True)
        return run.returncode,run.stdout,run.stderr


class R7V2ExactPackageTests(unittest.TestCase):
    def test_historical_v2_zip_manifest_and_p2_source_supersession(self):
        self.assertEqual(hashlib.sha256(V2.read_bytes()).hexdigest(),
                         EXPECTED_V2_ZIP)
        with ZipFile(V2) as z:
            self.assertEqual(len(z.namelist()),21)
            self.assertEqual(set(z.namelist()),
                             set(NAMES)|{'SOURCE-MANIFEST.sha256'})
            self.assertEqual(len(z.namelist()),len(set(z.namelist())))
            manifest=z.read('SOURCE-MANIFEST.sha256')
            self.assertEqual(hashlib.sha256(manifest).hexdigest(),
                             EXPECTED_V2_MANIFEST)
            for line,expected in zip(manifest.decode('ascii').splitlines(),
                                     NAMES,strict=True):
                digest,name=line.split('  ',1)
                self.assertEqual(name,expected)
                archived=z.read(name)
                self.assertEqual(hashlib.sha256(archived).hexdigest(),digest)
                if name in P2_SUPERSEDED:
                    self.assertNotEqual(archived,(ROOT/name).read_bytes())
            self.assertNotIn(
                b'from .g4_candidate import NoWriteTransport',
                z.read('fortis_approvals/r7_unified_server.py'))
            self.assertIn(
                b'from .r7_unified_candidate import NoWriteTransport',
                z.read('fortis_approvals/r7_unified_server.py'))

    def test_v1_failure_reproduced_and_v2_exact_zip_import_success(self):
        code,stdout,stderr=isolated_import(V1)
        self.assertNotEqual(code,0)
        self.assertIn(
            "No module named 'fortis_approvals.g4_candidate'",stderr)
        self.assertNotIn('FORTIS_R7_UNIFIED_READ_ASK_IMPORTS_PASS',stdout)
        code,stdout,stderr=isolated_import(V2)
        self.assertEqual(code,0,stderr)
        self.assertEqual(stdout,EXPECTED_IMPORT)
        self.assertEqual(stderr,'')
        print('R7_V1_BROKEN_IMPORT_REPRODUCED_PASS')
        print('R7_V2_EXACT_REVIEW_ZIP_ISOLATED_IMPORT_PASS')

    def test_build_script_new_owner_workfile_exact_pin_and_image_only(self):
        raw=SOURCE.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),EXPECTED_V2_BUILD)
        self.assertEqual(raw,TRANSFER.read_bytes())
        s=raw.decode('utf-8')
        for key in (EXPECTED_V2_ZIP,EXPECTED_V2_MANIFEST,EXPECTED_TAG,
                    'fortis-r7-unified-source-review-v2-20261101.zip',
                    'R7_REVIEW_IMAGE_TAG_ALREADY_EXISTS_NO_OVERWRITE',
                    'R7_SOURCE_FILE_COUNT_MISMATCH',
                    'R7_BUILD_CONTEXT_HAS_UNEXPECTED_FILES',
                    '--no-cache --pull=false',
                    'FORTIS_R7_CONTAINERS_STARTED=NONE',
                    'FORTIS_R7_TRUSTED_ADMISSION=OPEN'):
            with self.subTest(key=key):
                self.assertIn(key,s)
        for old in (
            'review-20261101-b0055e19',
            'fortis-r7-unified-source-review-20261101.zip',
            'b0055e1954174b11794de787f1eff17506b68610859677e463df8eb94ae12cb9'
        ):
            self.assertNotIn(old,s)
        self.assertEqual(s.count('    \'fortis_approvals/'),20)
        self.assertEqual(s.count('& docker build --no-cache'),1)
        for forbidden in (
            '& docker run', '& docker stop','& docker start','& docker restart',
            '& docker compose', '& docker exec',
            '& docker volume', '& docker update'
        ):
            self.assertNotIn(forbidden,s)


if __name__=='__main__':
    unittest.main()

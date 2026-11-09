#!/usr/bin/env python3
"""CI publication barriers and frozen build identity; isolated files only."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
CI = load('rdg_ci_test_target', ROOT / 'tools/rdg-ci.py')
PKG = load('rdg_ci_package_test_target', ROOT / 'tools/rdg-server-package.py')
SERVER = load('rdg_ci_server_test_target', ROOT / 'tools/rdg-server.py')


class Pipeline(unittest.TestCase):
    def test_core_integration_and_legacy_guards_are_mandatory_gates(self):
        self.assertEqual(len(CI.PYTHON_TESTS),len(set(CI.PYTHON_TESTS)))
        for name in ('rdg-decision-integration.test.py','rdg-native-dependencies.test.py','rdg-locks.test.py'):
            self.assertIn(name,CI.PYTHON_TESTS)
        for name in CI.PYTHON_TESTS:self.assertTrue((ROOT/'tests'/name).is_file(),name)

    def test_shared_fixture_uses_runner_temp_and_cleans_up(self):
        import os
        import sys
        with tempfile.TemporaryDirectory(prefix='rdg-runner-temp-') as tmp:
            runner_temp = Path(tmp) / 'runner temp with spaces'; runner_temp.mkdir()
            script = """from importlib.machinery import SourceFileLoader
from pathlib import Path
import os, sys
root = Path(sys.argv[1])
fixture = SourceFileLoader('runner_portable_fixture', str(root/'tests/rdg-portable-store.test.py')).load_module()
case = fixture.PortableStore()
try:
    case.setUp()
    base = case.base
    assert base.parent.resolve() == Path(os.environ['TMPDIR']).resolve(), str(base)
    assert case.authority.path.is_file()
finally:
    case.doCleanups()
assert not base.exists()
"""
            env = dict(os.environ, TMPDIR=str(runner_temp), TMP=str(runner_temp),
                       TEMP=str(runner_temp), PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1')
            result = subprocess.run([sys.executable, '-B', '-c', script, str(ROOT)],
                                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(list(runner_temp.iterdir()), [])

    def test_checked_failure_reports_bounded_tail_and_retains_full_log(self):
        import contextlib
        import io
        import os
        import sys
        with tempfile.TemporaryDirectory(prefix='rdg-ci-failure-') as tmp:
            base = Path(tmp); script = base/'failure.py'; log = base/'failure.log'
            script.write_text("import sys\nfor i in range(3000): print('earlier-%04d ' % i + 'x'*100)\nsys.stdout.flush()\nprint('SYNTHETIC_CI_FAILURE_DETAIL', file=sys.stderr)\nsys.exit(7)\n")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                with self.assertRaises(subprocess.CalledProcessError) as failure:
                    CI.checked([sys.executable, '-B', str(script)], log, os.environ.copy(), timeout_seconds=5)
            self.assertEqual(failure.exception.returncode, 7)
            self.assertGreater(log.stat().st_size, 200000)
            self.assertIn('SYNTHETIC_CI_FAILURE_DETAIL', log.read_text())
            self.assertIn('SYNTHETIC_CI_FAILURE_DETAIL', output.getvalue())
            self.assertNotIn('earlier-0000 ', output.getvalue())
            self.assertLess(len(output.getvalue().encode()), 20000)

    def test_fingerprint_tracks_uncommitted_added_changed_and_deleted_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); subprocess.run(['git', 'init', '-q', temp], check=True)
            (root / 'tools').mkdir(); source = root / 'tools/test.py'; source.write_text('first')
            before = CI.fingerprint(root); source.write_text('second')
            self.assertNotEqual(before, CI.fingerprint(root))
            source.unlink(); self.assertNotEqual(before, CI.fingerprint(root))
            source.symlink_to('/etc/passwd')
            with self.assertRaisesRegex(ValueError, 'CI_SOURCE_SYMLINK'):CI.fingerprint(root)

    def test_failed_or_changed_source_cannot_replace_previous_ready_release(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp); ready = out / 'ready.json'; ready.write_bytes(b'previous accepted release')
            artifact = out / 'RDG-Server-ci-test.zip'; artifact.write_bytes(b'test')
            with patch.object(CI, 'verify_unchanged', side_effect=ValueError('CI_SOURCE_CHANGED')):
                with self.assertRaisesRegex(ValueError, 'CI_SOURCE_CHANGED'):
                    CI.publish(out, artifact, 'ci-test', '0' * 64)
            self.assertEqual(ready.read_bytes(), b'previous accepted release')

    def test_success_publishes_complete_hash_bound_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp); artifact = out / 'RDG-Server-ci-test.zip'; artifact.write_bytes(b'checked package')
            with patch.object(CI, 'verify_unchanged'):
                result = CI.publish(out, artifact, 'ci-test', '1' * 64)
            self.assertEqual(json.loads((out / 'ready.json').read_text()), result)
            self.assertEqual(result['checks'], 'full'); self.assertEqual(result['bytes'], 15)
            self.assertNotIn('token', json.dumps(result))

    def test_artifact_contains_matching_manifest_runtime_identity_and_no_user_data(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'release.zip'; PKG.build(file, 'ci-isolated-test-123')
            with zipfile.ZipFile(file) as archive:
                manifest = json.loads(archive.read('RDG-Server/BUILD.json'))
                identity = json.loads(archive.read('RDG-Server/runtime/RDG-BUILD.json'))
                self.assertEqual(manifest['serverBuild'], identity['buildId'])
                self.assertEqual(manifest['imageTag'], identity['buildId'])
                self.assertFalse(manifest['includesUserData'])
                for name in ('rdg-portable-service','rdg-compact-read','rdg-batch','rdg-questions'):
                    self.assertIn('RDG-Server/runtime/tools/'+name+'.py',archive.namelist())
                self.assertTrue(all('secret' not in name and '/data/' not in name for name in archive.namelist()))
                import hashlib
                for name, digest in manifest['files'].items():
                    self.assertEqual(hashlib.sha256(archive.read('RDG-Server/' + name)).hexdigest(), digest)
            with self.assertRaisesRegex(ValueError, 'CHOOSE_NEW_ZIP_OUTPUT'):PKG.build(file)

    def test_checked_timeout_reaps_test_owned_descendants(self):
        # Synthetic process tree only; never exercise or signal a live RDG PID.
        import os
        import sys
        import time
        with tempfile.TemporaryDirectory(prefix='rdg-ci-cleanup-') as tmp:
            base = Path(tmp); script = base / 'parent.py'; child_pid = base / 'child.pid'
            script.write_text("""import os,signal,subprocess,sys,time
kid=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
open(sys.argv[1],'w').write(str(kid.pid))
def shutdown(sig,frame):
    kid.terminate()
    try:kid.wait(timeout=2)
    except subprocess.TimeoutExpired:kid.kill();kid.wait()
    raise SystemExit(143)
signal.signal(signal.SIGTERM,shutdown)
time.sleep(60)
""")
            log = base / 'timeout.log'
            with self.assertRaises(subprocess.TimeoutExpired):
                CI.checked([sys.executable,'-B',str(script),str(child_pid)],
                           log,os.environ.copy(),timeout_seconds=.5)
            self.assertTrue(child_pid.is_file(), 'child started before timeout')
            pid = int(child_pid.read_text())
            self.assertFalse((Path('/proc') / str(pid)).exists(),
                             'CI must both stop and reap the timed-out child')

    def test_checked_reaps_orphan_from_successful_test(self):
        # A child intentionally outlives its launcher: CI must terminate it
        # and reap it locally, not leave it a zombie under `sleep infinity`.
        import os
        import sys
        with tempfile.TemporaryDirectory(prefix='rdg-ci-orphan-') as tmp:
            base=Path(tmp);script=base/'launcher.py';child_pid=base/'pid.txt'
            script.write_text("""import subprocess,sys
kid=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
open(sys.argv[1],'w').write(str(kid.pid))
""")
            CI.checked([sys.executable,'-B',str(script),str(child_pid)],
                       base/'success.log',os.environ.copy(),timeout_seconds=4)
            pid=int(child_pid.read_text())
            self.assertFalse((Path('/proc')/str(pid)).exists(),
                             'CI must reap the orphan, not only SIGTERM it')

    def test_checked_success_runs_in_isolated_process_group(self):
        import os
        import sys
        with tempfile.TemporaryDirectory(prefix='rdg-ci-group-') as tmp:
            log=Path(tmp)/'success.log'
            CI.checked([sys.executable,'-c',
                       'import os;print(os.getpid()==os.getpgrp())'],
                       log,os.environ.copy(),timeout_seconds=3)
            self.assertEqual(log.read_text().strip(),'True')

    def test_runtime_build_identity_accepts_only_public_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'build.json'
            self.assertEqual(SERVER.build_identity(path), 'source')
            good = {'buildId': 'ci-test-123', 'contentSHA256': '0' * 64, 'repositoryHead': '1' * 40}
            path.write_text(json.dumps(good)); self.assertEqual(SERVER.build_identity(path), 'ci-test-123')
            good['token'] = 'must never become public'; path.write_text(json.dumps(good))
            with self.assertRaises(ValueError):SERVER.build_identity(path)


if __name__ == '__main__':
    unittest.main(verbosity=2)

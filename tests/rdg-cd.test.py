#!/usr/bin/env python3
"""Execute the real updater under PowerShell with isolated Docker/health fixtures.

This verifies publication consumption and rejection barriers, not a Docker engine
or a Windows deployment. No live credentials, app data or host tools are used.
"""
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PWSH = os.environ.get('RDG_TEST_PWSH') or shutil.which('pwsh') or '/workspace/repo/Workfiles/rdg-ci-pwsh-7.6.9/pwsh'
FIXED = ['Dockerfile', '.dockerignore', 'compose.yaml', 'compose.local.yaml', 'compose.https.yaml',
         'Caddyfile', 'Caddyfile.local', 'Start-RDG.ps1', 'Stop-RDG.ps1', 'Update-RDG.ps1']
BUILD = 'ci-isolated-cd-test-123'


def sha(raw):return hashlib.sha256(raw).hexdigest()


class Deploy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rdg-cd-test-')
        self.root = Path(self.temp.name); self.bootstrap = self.root / 'bootstrap'
        self.bootstrap.mkdir(); self.marker = self.root / 'started.txt'
        self.files = {name: b'# trusted deployment fixture\n' for name in FIXED}
        self.files['Update-RDG.ps1'] = (ROOT / 'deploy/rdg-server/Update-RDG.ps1').read_bytes()
        self.files['Start-RDG.ps1'] = b'''param($Mode,$AgentContainer,$PackageDirectory,[switch]$SkipSetup,$Domain)
if (-not $SkipSetup) { throw 'Updater must not run setup' }
[IO.File]::WriteAllText($env:RDG_TEST_START_MARKER,$PackageDirectory)
'''
        for name, raw in self.files.items():(self.bootstrap / name).write_bytes(raw)
        (self.bootstrap / 'BUILD.json').write_text(json.dumps({'files': {n: sha(r) for n, r in self.files.items()}}))

    def tearDown(self):self.temp.cleanup()

    def invoke_ready_bootstrap(self, pinned_sha, *, ready_race=False):
        script=self.root/'invoke-ready.ps1'
        script.write_text('''$global:RDGReadyReads=0
function global:docker {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Rest)
    if ($Rest.Count -ne 3 -or $Rest[0] -ne 'cp') { throw 'Unexpected Docker operation' }
    $name=($Rest[1] -split '/')[-1]
    if ($name -eq 'ready.json') {
        $global:RDGReadyReads+=1
        if ($env:RDG_TEST_READY_RACE -eq '1' -and $global:RDGReadyReads -eq 2) {
            Copy-Item -LiteralPath (Join-Path $env:RDG_TEST_FIXTURE 'new-ready.json') -Destination (Join-Path $env:RDG_TEST_FIXTURE 'ready.json') -Force
        }
    }
    if ($name -ne 'ready.json' -and $name -notmatch '^RDG-Server-ci-[a-z0-9-]+\\.zip$') { throw 'Unexpected source' }
    Copy-Item -LiteralPath (Join-Path $env:RDG_TEST_FIXTURE $name) -Destination $Rest[2]
    $global:LASTEXITCODE=0
}
& $env:RDG_TEST_BOOTSTRAP -AgentContainer '000000000001' -ExpectedBuildId $env:RDG_TEST_BUILD -PinnedSha256 $env:RDG_TEST_PIN
''')
        env=dict(os.environ,RDG_TEST_FIXTURE=str(self.root),RDG_TEST_BUILD=BUILD,
            RDG_TEST_BOOTSTRAP=str(ROOT/'deploy/rdg-server/Invoke-RDG-Ready-Once.ps1'),
            RDG_TEST_PIN=pinned_sha,RDG_TEST_READY_RACE='1' if ready_race else '0',
            LOCALAPPDATA=str(self.root),RDG_TEST_START_MARKER=str(self.marker))
        return subprocess.run([PWSH,'-NoLogo','-NoProfile','-NonInteractive','-File',str(script)],
                              env=env,text=True,capture_output=True,timeout=30)

    def test_ready_bootstrap_rejects_wrong_pin_before_running_the_updater(self):
        self.release()
        result=self.invoke_ready_bootstrap('0'*64)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('pinned checksum',result.stdout+result.stderr)
        self.assertFalse(self.marker.exists())

    def test_ready_bootstrap_rejects_a_changed_ready_pointer_before_update(self):
        self.release();ready=json.loads((self.root/'ready.json').read_text());pinned=ready['sha256']
        ready['buildId']='ci-another-ready-release';(self.root/'ready.json').write_text(json.dumps(ready))
        result=self.invoke_ready_bootstrap(pinned)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('READY now points to another CI release',result.stdout+result.stderr)
        self.assertFalse(self.marker.exists())

    def test_ready_bootstrap_installs_the_exact_matching_pin(self):
        self.release();ready=json.loads((self.root/'ready.json').read_text())
        with self.health():result=self.invoke_ready_bootstrap(ready['sha256'])
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue(self.marker.exists())
        self.assertEqual(Path(self.marker.read_text()).name,BUILD)

    def test_ready_bootstrap_pins_the_updater_across_a_late_ready_race(self):
        global BUILD
        self.release();original=json.loads((self.root/'ready.json').read_text());reviewed_build=BUILD
        try:
            BUILD='ci-bootstrap-race-newer';self.release()
        finally:BUILD=reviewed_build
        newer=json.loads((self.root/'ready.json').read_text())
        (self.root/'new-ready.json').write_text(json.dumps(newer))
        (self.root/'ready.json').write_text(json.dumps(original))
        result=self.invoke_ready_bootstrap(original['sha256'],ready_race=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Pinned CI release mismatch',result.stdout+result.stderr)
        self.assertFalse(self.marker.exists(),'a newer unreviewed release must never start')

    def release(self, mutate=None, extra=None, wrong_digest=False, corrupt=False):
        payload = dict(self.files, **{'runtime/RDG-BUILD.json': json.dumps({'buildId': BUILD}).encode()})
        if mutate:mutate(payload)
        manifest = {'kind': 'rdg-personal-server-package', 'serverBuild': BUILD, 'imageTag': BUILD,
                    'includesUserData': False, 'files': {n: sha(r) for n, r in payload.items()}}
        if wrong_digest:manifest['files']['runtime/RDG-BUILD.json'] = '0' * 64
        payload['BUILD.json'] = json.dumps(manifest).encode()
        archive = self.root / ('RDG-Server-' + BUILD + '.zip')
        with zipfile.ZipFile(archive, 'w') as z:
            for name, raw in payload.items():z.writestr('RDG-Server/' + name, raw)
            if extra:z.writestr(extra, b'unsafe')
        raw = archive.read_bytes()
        ready = {'schemaVersion': 1, 'kind': 'rdg-ci-release', 'buildId': BUILD, 'artifact': archive.name,
                 'sha256': sha(raw), 'bytes': len(raw), 'sourceSHA256': '1' * 64,
                 'checks': 'full', 'createdAt': '2026-10-29T00:00:00Z'}
        (self.root / 'ready.json').write_text(json.dumps(ready))
        if corrupt:archive.write_bytes(raw + b'corrupt')

    def invoke(self, native=False, fail_copy=False):
        script = self.root / 'invoke.ps1'
        fake = '''function global:docker {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Rest)
    if ($Rest.Count -ne 3 -or $Rest[0] -ne 'cp') { throw 'Unexpected Docker operation' }
    $name = ($Rest[1] -split '/')[-1]
    if ($name -ne 'ready.json' -and $name -ne ('RDG-Server-' + $env:RDG_TEST_BUILD + '.zip')) { throw 'Unexpected source' }
    Copy-Item -LiteralPath (Join-Path $env:RDG_TEST_FIXTURE $name) -Destination $Rest[2]
    $global:LASTEXITCODE = 0
}
'''
        invoke = "& (Join-Path $env:RDG_TEST_FIXTURE 'bootstrap/Update-RDG.ps1') -AgentContainer worker -StateDirectory (Join-Path $env:RDG_TEST_FIXTURE 'state')\n"
        script.write_text(('' if native else fake) + invoke)
        env = dict(os.environ, RDG_TEST_FIXTURE=str(self.root), RDG_TEST_START_MARKER=str(self.marker),
                   RDG_TEST_BUILD=BUILD, LOCALAPPDATA=str(self.root))
        if native:
            # /tmp is mounted noexec in Repo Docker: use the executable Workfiles
            # mount for the fake native command, and clean only this test's files.
            native_root = tempfile.TemporaryDirectory(
                prefix='rdg-cd-native-', dir=os.environ.get('RDG_WORKFILES', '/workspace/repo/Workfiles'))
            self.addCleanup(native_root.cleanup)
            fake_bin = Path(native_root.name) / 'mock-bin'
            fake_bin.mkdir()
            docker = fake_bin / 'docker'
            docker.write_text('''#!/usr/bin/env python3
import os, pathlib, shutil, sys
if len(sys.argv) != 4 or sys.argv[1] != 'cp':
    print('Unexpected Docker operation', file=sys.stderr); sys.exit(18)
name = sys.argv[2].split('/')[-1]
if name not in ('ready.json', 'RDG-Server-' + os.environ['RDG_TEST_BUILD'] + '.zip'):
    print('Unexpected Docker source', file=sys.stderr); sys.exit(19)
if os.environ.get('RDG_TEST_COPY_FAIL') == '1':
    print('simulated docker cp failure', file=sys.stderr); sys.exit(17)
shutil.copyfile(str(pathlib.Path(os.environ['RDG_TEST_FIXTURE']) / name), sys.argv[3])
print('fake docker output on stdout')
print('Successfully copied 429B (fake Docker stderr progress)', file=sys.stderr)
''')
            docker.chmod(0o755)
            env['PATH'] = str(fake_bin) + os.pathsep + env['PATH']
            if fail_copy:env['RDG_TEST_COPY_FAIL'] = '1'
        return subprocess.run([PWSH, '-NoLogo', '-NoProfile', '-File', str(script)],
            env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=40)

    @contextmanager
    def health(self, build=BUILD):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                raw = json.dumps({'status': 'ok', 'service': 'rdg', 'buildId': build}).encode()
                self.send_response(200); self.send_header('Content-Length', str(len(raw)))
                self.end_headers(); self.wfile.write(raw)
            def log_message(self, *args):pass
        HTTPServer.allow_reuse_address = True
        server = HTTPServer(('127.0.0.1', 18880), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:yield
        finally:server.shutdown(); server.server_close(); thread.join()

    def test_windows_utf8_bom_in_private_api_check_json(self):
        # Exercise the actual Python stdin parser embedded in Start-RDG.ps1.
        # Windows PowerShell can prepend UTF-8 BOM when piping to docker exec.
        source = (ROOT / 'deploy/rdg-server/Start-RDG.ps1').read_text(encoding='utf-8')
        head = source.split("$connectCode = @'\n", 1)[1].split("\n'@", 1)[0]
        python_prelude = head.split('with urllib.request.build_opener', 1)[0]
        payload = json.dumps({'profile':'gateway','origin':'http://rdg-api-gateway:8081',
                              'namespaceId':'12345678-1234-4234-8234-123456789abc'}).encode('utf-8')
        for raw in (payload, b'\xef\xbb\xbf' + payload):
            result = subprocess.run([sys.executable, '-c', python_prelude + "print(context['profile'])"],
                                    input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            self.assertEqual(result.stdout.strip(), b'gateway')

    def test_accepts_matching_frozen_release_and_repeat_is_idempotent(self):
        self.release()
        with self.health():
            result = self.invoke(); self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(self.marker.exists())
            before = (self.root / 'state/active.json').read_bytes(); self.marker.unlink()
            repeat = self.invoke(); self.assertEqual(repeat.returncode, 0, repeat.stdout)
            self.assertFalse(self.marker.exists()); self.assertEqual(before, (self.root / 'state/active.json').read_bytes())

    def test_native_docker_copy_progress_is_silent_and_update_succeeds(self):
        self.release()
        with self.health():
            result = self.invoke(native=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn('Successfully copied', result.stdout)
        self.assertNotIn('fake docker output on stdout', result.stdout)
        self.assertIn('RDG updated:', result.stdout)
        self.assertTrue(self.marker.exists())

    def test_native_docker_failure_is_reported_not_silenced(self):
        self.release()
        result = self.invoke(native=True, fail_copy=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Cannot copy the prepared CI artifact', result.stdout)
        self.assertIn('simulated docker', result.stdout)
        self.assertIn('cp failure', result.stdout)
        self.assertFalse(self.marker.exists())

    def test_recorded_release_redeploys_when_live_build_is_stale(self):
        self.release()
        with self.health():
            result = self.invoke(); self.assertEqual(result.returncode, 0, result.stdout)
        recorded = (self.root / 'state/active.json').read_bytes()
        self.marker.unlink()
        with self.health(build='old-build'):
            result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('requested build', result.stdout)
        self.assertTrue(self.marker.exists(), 'A stale active.json must not skip deployment')
        self.assertEqual(recorded, (self.root / 'state/active.json').read_bytes())

    def test_corrupt_zip_never_starts_deployment(self):
        self.release(corrupt=True); result = self.invoke()
        self.assertNotEqual(result.returncode, 0); self.assertIn('hash/size mismatch', result.stdout)
        self.assertFalse(self.marker.exists())

    def test_changed_runtime_without_matching_manifest_is_rejected(self):
        self.release(wrong_digest=True); result = self.invoke()
        self.assertNotEqual(result.returncode, 0); self.assertIn('file hash mismatch', result.stdout)
        self.assertFalse(self.marker.exists())

    def test_changed_compose_cannot_be_automatically_executed(self):
        self.release(mutate=lambda p: p.update({'compose.yaml': b'services: dangerous host mount'}))
        result = self.invoke(); self.assertNotEqual(result.returncode, 0)
        self.assertIn('Deployment config changed', result.stdout); self.assertFalse(self.marker.exists())

    def test_zip_path_escape_is_rejected_before_extraction(self):
        self.release(extra='RDG-Server/../../escape.txt'); result = self.invoke()
        self.assertNotEqual(result.returncode, 0); self.assertIn('Unsafe', result.stdout)
        self.assertFalse(self.marker.exists()); self.assertFalse((self.root / 'escape.txt').exists())

    def test_wrong_running_build_is_not_marked_as_success(self):
        self.release()
        with self.health(build='old-build'):
            result = self.invoke()
        self.assertNotEqual(result.returncode, 0); self.assertIn('requested build', result.stdout)
        self.assertTrue(self.marker.exists()); self.assertFalse((self.root / 'state/active.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)

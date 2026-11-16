#!/usr/bin/env python3
"""Run the real GitHub installer/updater with native gh and isolated CI data.

No GitHub network, live Docker engine, credentials or existing owners are used.
Linux PowerShell execution is not native Windows acceptance.
"""
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PWSH = os.environ.get('RDG_TEST_PWSH') or shutil.which('pwsh') or '/workspace/repo/Workfiles/rdg-ci-pwsh-7.6.9/pwsh'
FIXED = ['Dockerfile', '.dockerignore', 'compose.yaml', 'compose.local.yaml', 'compose.https.yaml',
         'Caddyfile', 'Caddyfile.local', 'Start-RDG.ps1', 'Stop-RDG.ps1', 'Update-RDG.ps1']
BUILD = 'ci-github-delivery-isolated-123'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def archive(payload):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name, raw in payload.items():
            z.writestr(name, raw)
    return stream.getvalue()


class GitHubDelivery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rdg-github-cd-',
            dir=os.environ.get('RDG_WORKFILES', '/workspace/repo/Workfiles'))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'source checkout with spaces'
        self.deploy = self.repo / 'deploy/rdg-server'
        self.deploy.mkdir(parents=True)
        self.marker = self.root / 'started.txt'
        self.calls = self.root / 'gh-calls.jsonl'
        self.local = self.root / 'local app data'
        self.fixed = {name: b'# trusted fixture\n' for name in FIXED}
        self.fixed['Update-RDG.ps1'] = (ROOT / 'deploy/rdg-server/Update-RDG.ps1').read_bytes()
        self.fixed['Start-RDG.ps1'] = b'''param($Mode,$AgentContainer,$PackageDirectory,[switch]$SkipSetup,$Domain)
if (-not $SkipSetup) { throw 'Do not initialize data on update' }
[IO.File]::WriteAllText($env:RDG_TEST_START_MARKER,$PackageDirectory)
'''
        for name, raw in self.fixed.items():
            (self.deploy / name).write_bytes(raw)
        shutil.copyfile(ROOT / 'deploy/rdg-server/Install-RDGFromGitHub.ps1',
                        self.deploy / 'Install-RDGFromGitHub.ps1')
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'RDG isolated test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'core.autocrlf', 'false')
        self.git('add', '--all')
        self.git('commit', '-m', 'isolated trusted checkout')
        self.head = self.git('rev-parse', 'HEAD').strip()
        self.git('remote', 'add', 'origin', 'https://github.com/AlexPastukhh/rd-graphs.git')
        self.git('update-ref', 'refs/remotes/origin/main', self.head)
        self.git('config', 'branch.main.remote', 'origin')
        self.git('config', 'branch.main.merge', 'refs/heads/main')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        gh = self.bin / 'gh'
        gh.write_text("""#!/usr/bin/env python3
import json, os, pathlib, sys
root=pathlib.Path(os.environ['RDG_GITHUB_FIXTURE'])
spec=json.loads((root/'api.json').read_text())
args=sys.argv[1:]; path=args[-1]
with (root/'gh-calls.jsonl').open('a') as f: f.write(json.dumps(args)+'\\n')
if args[:6] != ['api','--hostname','github.com','--method','GET','-H']:
    sys.exit(23)
if path.endswith('/zip'):
    if spec.get('downloadFail'): sys.exit(24)
    sys.stdout.buffer.write((root/'artifact.zip').read_bytes())
    print('native progress on stderr',file=sys.stderr)
else:
    key=path.removeprefix('repos/AlexPastukhh/rd-graphs/')
    if key not in spec: sys.exit(25)
    value=spec[key]
    if key=='branches/main' and spec.get('mainRace'):
        calls=(root/'gh-calls.jsonl').read_text().count('branches/main')
        if calls>1: value={'commit':{'sha':'0'*40}}
    print(json.dumps(value))
""")
        gh.chmod(0o755)
        self.release()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args],
                                       text=True, stderr=subprocess.DEVNULL)

    def release(self, *, manifest_head=None, inner_extra=None, changed_compose=False, outer_extra=None):
        payload = dict(self.fixed)
        if changed_compose:
            payload['compose.yaml'] = b'services: unreviewed\n'
        payload['runtime/RDG-BUILD.json'] = json.dumps({'buildId': BUILD,
                                                       'repositoryHead': self.head}).encode()
        manifest = {'kind': 'rdg-personal-server-package', 'serverBuild': BUILD,
                    'imageTag': BUILD, 'repositoryHead': manifest_head or self.head,
                    'includesUserData': False, 'files': {n: sha(r) for n, r in payload.items()}}
        payload['BUILD.json'] = json.dumps(manifest).encode()
        inner = {'RDG-Server/' + n: r for n, r in payload.items()}
        if inner_extra:
            inner[inner_extra] = b'unsafe'
        raw = archive(inner)
        self.ready = {'schemaVersion': 1, 'kind': 'rdg-ci-release', 'buildId': BUILD,
                      'artifact': 'RDG-Server-' + BUILD + '.zip', 'sha256': sha(raw),
                      'bytes': len(raw), 'sourceSHA256': '1' * 64, 'checks': 'full',
                      'createdAt': '2026-11-16T00:00:00Z'}
        outer = {'ready.json': json.dumps(self.ready).encode(), self.ready['artifact']: raw}
        if outer_extra:
            outer[outer_extra] = b'unsafe'
        raw = archive(outer)
        (self.root / 'artifact.zip').write_bytes(raw)
        self.pin = sha(raw)
        repo = {'id': 1, 'full_name': 'AlexPastukhh/rd-graphs'}
        self.spec = {
            'branches/main': {'commit': {'sha': self.head}},
            'actions/workflows/rdg-ci.yml': {'id': 12, 'path': '.github/workflows/rdg-ci.yml', 'state': 'active'},
            'actions/runs/77': {'id': 77, 'run_attempt': 1, 'workflow_id': 12,
                'path': '.github/workflows/rdg-ci.yml', 'head_sha': self.head, 'head_branch': 'main',
                'repository': repo, 'head_repository': repo, 'status': 'completed',
                'conclusion': 'success', 'event': 'push'},
            'actions/artifacts/88': {'id': 88, 'name': 'rdg-server-' + self.head,
                'size_in_bytes': len(raw), 'digest': 'sha256:' + self.pin, 'expired': False,
                'workflow_run': {'id': 77, 'head_sha': self.head, 'head_branch': 'main',
                                 'repository_id': 1, 'head_repository_id': 1}}}

    def invoke(self, apply=True, pin=None):
        (self.root / 'api.json').write_text(json.dumps(self.spec))
        env = dict(os.environ, RDG_GITHUB_FIXTURE=str(self.root), LOCALAPPDATA=str(self.local),
                   RDG_TEST_START_MARKER=str(self.marker),
                   PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                   DOTNET_SYSTEM_GLOBALIZATION_INVARIANT='1')
        args = [PWSH, '-NoLogo', '-NoProfile', '-NonInteractive', '-File',
                str(self.deploy / 'Install-RDGFromGitHub.ps1'),
                '-ExpectedCommitSha', self.head, '-RunId', '77', '-RunAttempt', '1',
                '-ArtifactId', '88', '-PinnedArtifactSha256', pin or self.pin,
                '-AgentContainer', '000000000001']
        if apply:
            args.append('-Apply')
        return subprocess.run(args, env=env, text=True, capture_output=True, timeout=40)

    @contextmanager
    def health(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                raw = json.dumps({'status': 'ok', 'service': 'rdg', 'buildId': BUILD}).encode()
                self.send_response(200); self.send_header('Content-Length', str(len(raw)))
                self.end_headers(); self.wfile.write(raw)
            def log_message(self, *args):
                pass
        HTTPServer.allow_reuse_address = True
        server = HTTPServer(('127.0.0.1', 18880), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def assert_refused(self, expected):
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(expected, result.stdout + result.stderr)
        self.assertFalse(self.marker.exists())
        self.assertFalse(list(self.local.glob('RDG-Server/cicd/github-install-*.json')))
        self.assertFalse(list(self.local.glob('RDG-Server/cicd/github-transfer-*')))

    def test_pinned_main_artifact_installs_and_leaves_source_clean(self):
        before = {p.relative_to(self.repo).as_posix(): sha(p.read_bytes())
                  for p in self.repo.rglob('*') if p.is_file()}
        with self.health():
            result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.marker.exists())
        receipt = json.loads(next(self.local.glob('RDG-Server/cicd/github-install-*.json')).read_text())
        self.assertEqual(receipt['sourceCommit'], self.head)
        self.assertEqual(receipt['artifactSHA256'], self.pin)
        self.assertEqual(receipt['payloadSHA256'], self.ready['sha256'])
        self.assertTrue(receipt['healthVerified'])
        self.assertEqual(self.git('status', '--porcelain'), '')
        after = {p.relative_to(self.repo).as_posix(): sha(p.read_bytes())
                 for p in self.repo.rglob('*') if p.is_file()}
        self.assertEqual(before, after, 'including the Git index and ignored files')
        self.assertNotIn('native progress', result.stdout + result.stderr)
        self.assertFalse(list(self.local.glob('RDG-Server/cicd/github-transfer-*')))

    def test_preview_validates_real_package_without_start_or_active_release(self):
        result = self.invoke(apply=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('RDG_GITHUB_PREVIEW_PASS', result.stdout)
        self.assertFalse(self.marker.exists())
        self.assertFalse((self.local / 'RDG-Server/cicd/active.json').exists())
        self.assertFalse((self.local / 'RDG-Server/cicd' / BUILD).exists())

    def test_dirty_source_is_refused_before_github_or_download(self):
        (self.repo / 'uncommitted.txt').write_text('preserve me')
        self.assert_refused('clean, pinned main')
        self.assertFalse(self.calls.exists())
        self.assertEqual((self.repo / 'uncommitted.txt').read_text(), 'preserve me')

    def test_wrong_origin_is_refused(self):
        self.git('remote', 'set-url', 'origin', 'https://example.invalid/rdg.git')
        self.assert_refused('canonical origin/upstream')

    def test_wrong_artifact_pin_is_refused(self):
        result = self.invoke(pin='0' * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('provenance mismatch', result.stdout + result.stderr)
        self.assertFalse(self.marker.exists())

    def test_invalid_run_and_artifact_provenance_are_refused(self):
        cases = [
            ('actions/runs/77', 'conclusion', 'failure', 'successful main run'),
            ('actions/runs/77', 'event', 'pull_request', 'successful main run'),
            ('actions/runs/77', 'run_attempt', 2, 'successful main run'),
            ('actions/runs/77', 'head_sha', '0' * 40, 'successful main run'),
            ('actions/runs/77', 'head_repository', {'full_name': 'other/fork'}, 'successful main run'),
            ('actions/artifacts/88', 'expired', True, 'provenance mismatch'),
            ('actions/artifacts/88', 'workflow_run', {'id': 999}, 'provenance mismatch'),
        ]
        for key, field, value, message in cases:
            with self.subTest(field=field):
                self.release()
                self.spec[key][field] = value
                self.assert_refused(message)

    def test_corrupt_download_is_refused_before_deployment(self):
        p = self.root / 'artifact.zip'
        p.write_bytes(p.read_bytes()[:-1] + b'X')
        self.assert_refused('artifact ZIP hash/size mismatch')

    def test_unsafe_outer_zip_never_extracts(self):
        self.release(outer_extra='../../escape.txt')
        self.assert_refused('exactly READY')
        self.assertFalse((self.root / 'escape.txt').exists())

    def test_unsafe_inner_zip_is_refused_by_real_updater(self):
        self.release(inner_extra='RDG-Server/../../escape.txt')
        self.assert_refused('Unsafe or duplicate ZIP')
        self.assertFalse((self.root / 'escape.txt').exists())

    def test_other_repository_head_in_inner_manifest_is_refused(self):
        self.release(manifest_head='0' * 40)
        self.assert_refused('repository HEAD mismatch')

    def test_changed_downloaded_deployment_code_is_not_executed(self):
        self.release(changed_compose=True)
        self.assert_refused('Deployment config changed')

    def test_github_main_race_stops_before_deploy(self):
        self.spec['mainRace'] = True
        self.assert_refused('GitHub main changed')

    def test_failed_native_download_is_not_reported_as_success(self):
        self.spec['downloadFail'] = True
        self.assert_refused('Git/gh failed')


if __name__ == '__main__':
    unittest.main()

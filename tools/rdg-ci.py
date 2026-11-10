#!/usr/bin/env python3
"""Run isolated RDG checks and atomically publish a frozen release for Fortis_M."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
import shutil
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
WORKFILES = Path(os.environ.get('RDG_WORKFILES', '/workspace/repo/Workfiles'))


def atomic_json(path, value):
    fd, temporary = tempfile.mkstemp(prefix='.publish-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(value, out, indent=2); out.write('\n'); out.flush(); os.fsync(out.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


PYTHON_TESTS = (
    'rdg-decision-model.test.py', 'rdg-findings.test.py', 'rdg-analysis.test.py', 'rdg-history-view.test.py', 'rdg-current-example.test.py', 'rdg-example-journal.test.py', 'rdg-snapshot-validation.test.py', 'rdg-read-projection-digests.test.py', 'rdg-projection-cache.test.py', 'rdg-dependency-policies-v2.test.py', 'rdg-relation-read-cache.test.py', 'rdg-writer-calculation-cache.test.py',
    'rdg-portable-service.test.py', 'rdg-api-discovery.test.py', 'rdg-compact-read.test.py', 'rdg-scoped-read.test.py', 'rdg-markdown-search.test.py', 'rdg-batch.test.py', 'rdg-question-first-slice.test.py', 'rdg-questions-estimates.test.py', 'rdg-decision-theory.test.py', 'rdg-recommendations-authoring.test.py', 'rdg-planning-meta-actions.test.py', 'rdg-t1-t2-workflow.test.py', 'rdg-decision-integration.test.py',
    'rdg-native-dependencies.test.py', 'rdg-locks.test.py',
    'rdg-gateway.test.py', 'rdg-server.test.py', 'rdg-ci.test.py', 'rdg-cd.test.py',
)


def fingerprint(root=ROOT):
    names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others',
        '--exclude-standard', '--', 'tools', 'tests', 'deploy', 'docs', '.github',
        'AGENTS.md', 'README.md', '.gitignore', '.gitattributes', '.ignore'], cwd=root).split(b'\0')
    digest = hashlib.sha256()
    for name in sorted(set(n for n in names if n)):
        path = root / os.fsdecode(name)
        if path.is_symlink():
            raise ValueError('CI_SOURCE_SYMLINK:' + os.fsdecode(name))
        if path.is_file():
            digest.update(name + b'\0' + hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _adopt_test_orphans():
    """Linux: make the one-at-a-time CI runner a subreaper, not PID 1.

    Chromium can briefly outlive a Node parent; otherwise those exits are
    adopted by the container's `sleep infinity` and remain zombies forever.
    No kernel/global setting is modified; PR_SET_CHILD_SUBREAPER is local to
    this runner process and its descendants.
    """
    if sys.platform != 'linux':
        return
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), 'TEST_SUBREAPER_UNAVAILABLE')


def _collect_test_orphans():
    """Non-blocking wait for adopted *exited* test descendants only.

    CI runs checks serially and has already waited for its direct process.
    Reaping here cannot target a Docker service or unrelated PID 1 child.
    """
    if sys.platform != 'linux':
        return
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid:
            continue
        time.sleep(.05)


def _test_group_running(group):
    """Exclude zombies: they have stopped, but may still own their process group."""
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / 'stat').read_text().rsplit(') ', 1)[1].split()
            if fields[0] != 'Z' and int(fields[2]) == group:
                return True
        except (OSError, ValueError, IndexError):
            continue
    return False


def _reap_test_process_group(process):
    """Clean the unique POSIX session created for a CI check, never a shared group.

    A timed-out shell/Node can leave Chromium, Gunicorn workers and Caddy
    behind. Terminating only subprocess.run's direct child leaks them into the
    Docker PID cgroup. Always clean the test group, including on success.
    """
    group = process.pid  # start_new_session=True: never shared with a service.
    # Signal the whole TEST group first, not only the launching shell. Otherwise
    # bash can exit while Node is still cleaning detached Gunicorn/Caddy groups.
    try:
        os.killpg(group, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        # Do not waitpid(-1) here: Popen still owns the direct test process.
        # Reap adopted grandchildren only after process.wait() completes.
        if not _test_group_running(group):
            break
        time.sleep(.1)
    else:
        try:
            os.killpg(group, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.wait(timeout=3)


def _report_failed_check(log):
    """Show bounded diagnostics while retaining the complete per-check log."""
    print('CI failure log: ' + str(log), flush=True)
    try:
        with log.open('rb') as source:
            source.seek(0, os.SEEK_END)
            source.seek(max(0, source.tell() - 16384))
            tail = source.read(16384)
    except OSError as exc:
        print('CI failure log unavailable: ' + str(exc), flush=True)
        return
    lines = tail.decode('utf-8', errors='replace').splitlines()[-80:]
    if lines:
        print('\n'.join(lines), flush=True)


def checked(command, log, env, *, timeout_seconds=900):
    print('CI: ' + ' '.join(map(str, command)), flush=True)
    _adopt_test_orphans()
    with log.open('w') as out:
        process = subprocess.Popen(list(map(str, command)), cwd=ROOT, env=env,
                                   stdout=out, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            code = process.wait(timeout=timeout_seconds)
            if code != 0:
                _report_failed_check(log)
                raise subprocess.CalledProcessError(code, process.args)
        finally:
            try:
                _reap_test_process_group(process)
            finally:
                _collect_test_orphans()


def verify_unchanged(expected, root=ROOT):
    if fingerprint(root) != expected:
        raise ValueError('CI_SOURCE_CHANGED: discard this result; run checks on the new source')


def publish(outbox, artifact, build_id, source_sha, expected_source=None):
    verify_unchanged(expected_source or source_sha)
    value = {'schemaVersion': 1, 'kind': 'rdg-ci-release', 'buildId': build_id,
        'artifact': artifact.name, 'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
        'bytes': artifact.stat().st_size, 'sourceSHA256': source_sha,
        'checks': 'full', 'createdAt': datetime.now(timezone.utc).isoformat()}
    atomic_json(outbox / 'ready.json', value)
    return value


def run(outbox):
    outbox.mkdir(parents=True, exist_ok=True)
    with (outbox / 'pipeline.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f').lower()
        directory = outbox / ('run-' + stamp); directory.mkdir()
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1')
        for key in tuple(env):
            if key.startswith('RDG_AUTH_'):
                del env[key]
        started = time.monotonic()
        source_sha = fingerprint()
        try:
            checked([sys.executable, '-B', 'tools/build-rdg-layout.py'], directory / 'generate.log', env)
            source_sha = fingerprint()
            atomic_json(outbox / 'status.json', {'status': 'checking', 'sourceSHA256': source_sha,
                                                'logs': directory.name})
            for filename in PYTHON_TESTS:
                checked([sys.executable, '-B', 'tests/' + filename], directory / (filename + '.log'), env)
            checked(['node', '--test', 'tests/rdg-decision-contract.test.cjs',
                     'tests/rdg-decision-structure.test.cjs', 'tests/rdg-portable-ui.test.cjs',
                     'tests/rdg-visual-occurrences.test.cjs', 'tests/rdg-plan-view.test.cjs', 'tests/rdg-documentation.test.cjs'],
                    directory / 'node.log', env)
            verify_unchanged(source_sha)
            build_id = 'ci-' + stamp + '-' + source_sha[:10]
            spec = importlib.util.spec_from_file_location('rdg_ci_package', ROOT / 'tools/rdg-server-package.py')
            package = importlib.util.module_from_spec(spec); spec.loader.exec_module(package)
            artifact = outbox / ('RDG-Server-' + build_id + '.zip')
            package.build(artifact, build_id=build_id)
            browser_env = dict(env, RDG_SERVER_ARCHIVE=str(artifact),
                RDG_SERVER_PYTHON=env.get('RDG_SERVER_PYTHON',
                    str(WORKFILES / 'rdg-server-test-venv/bin/python3') if
                    (WORKFILES / 'rdg-server-test-venv/bin/python3').is_file() else sys.executable))
            fixtures = directory / 'fixtures'; fixtures.mkdir()
            browser_env['RDG_WORKFILES'] = str(fixtures)
            browser_env.setdefault('RDG_SERVER_CADDY', str(WORKFILES / 'rdg-server-caddy-2.11.7/caddy'))
            checked(['bash', 'tools/rdg-visual-test.sh', 'tests/visual/rdg-server.cjs'],
                    directory / 'browser.log', browser_env)
            checked(['bash', 'tools/rdg-visual-test.sh', 'tests/visual/rdg-decision-desktop.cjs'],
                    directory / 'desktop.log', browser_env)
            questions_browser_env = dict(browser_env, RDG_SCREENSHOT_DIR=str(fixtures))
            checked(['bash', 'tools/rdg-visual-test.sh', 'tests/visual/rdg-question-readonly.cjs'],
                    directory / 'questions-browser.log', questions_browser_env)
            checked(['bash', 'tools/rdg-visual-test.sh', 'tests/visual/rdg-question-editing.cjs'],
                    directory / 'questions-editing-browser.log', questions_browser_env)
            checked(['bash', 'tools/rdg-visual-test.sh', 'tests/visual/rdg-decision-theory.cjs'],
                    directory / 'theory-browser.log', questions_browser_env)
            checked(['bash', 'tools/rdg-visual-test.sh', 'tests/visual/rdg-recommendations-authoring.cjs'],
                    directory / 'recommendations-browser.log', questions_browser_env)
            checked(['bash', 'tools/rdg-visual-test.sh', 'tests/visual/rdg-planning-meta-actions.cjs'],
                    directory / 'meta-actions-browser.log', questions_browser_env)
            checked(['bash', 'tools/rdg-visual-test.sh', 'tests/visual/rdg-markdown-search.cjs'],
                    directory / 'markdown-search-browser.log', questions_browser_env)
            # These are freshly-created isolated test owners/profiles, never live RDG data.
            # Retain PNG/JSON evidence, discard only the large private fixture directories.
            for base in list(fixtures.glob('rdg-server-browser-*'))+list(fixtures.glob('rdg-decision-desktop-*')):
                for name in ('code with spaces', 'data', 'secrets', 'gateway-private',
                             'browser', 'fresh-browser', 'caddy-config', 'caddy-data'):
                    private = base / name
                    if private.is_dir() and not private.is_symlink():
                        shutil.rmtree(private)
            release = publish(outbox, artifact, build_id, source_sha)
            atomic_json(outbox / 'status.json', {'status': 'ready', 'buildId': build_id,
                'sourceSHA256': source_sha, 'logs': directory.name,
                'durationSeconds': round(time.monotonic() - started, 2)})
            print(json.dumps(release), flush=True)
            return source_sha
        except Exception as exc:
            atomic_json(outbox / 'status.json', {'status': 'failed', 'sourceSHA256': source_sha,
                'logs': directory.name, 'error': str(exc)[:1000]})
            print('CI failed; previous ready release retained: ' + str(exc), file=sys.stderr, flush=True)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outbox', type=Path, default=WORKFILES / 'rdg-ci')
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    if not args.outbox.is_absolute() or args.outbox == ROOT or ROOT in args.outbox.parents:
        parser.error('Use an absolute outbox outside the repository')
    if not args.watch:
        run(args.outbox); return
    args.outbox.mkdir(parents=True, exist_ok=True)
    watch_lock = (args.outbox / 'watch.lock').open('a')
    fcntl.flock(watch_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    (args.outbox / 'watch.pid').write_text(str(os.getpid()) + '\n')
    last = None
    ready = args.outbox / 'ready.json'
    if ready.is_file():
        try:
            old = json.loads(ready.read_text())
            if old.get('sourceSHA256') == fingerprint():
                last = old['sourceSHA256']
        except (ValueError, OSError):
            pass
    print('CI watch ready; source changes trigger isolated checks and release publication', flush=True)
    # The watcher is long-lived. Reload CI code itself before the next gate so
    # adding a mandatory test cannot silently leave the old runner in memory.
    runner_source = hashlib.sha256(Path(__file__).read_bytes()).digest()
    while True:
        if hashlib.sha256(Path(__file__).read_bytes()).digest() != runner_source:
            print('CI runner source changed: restarting watcher with updated gates', flush=True)
            watch_lock.close()
            os.execv(sys.executable, [sys.executable, '-B', str(Path(__file__).resolve()),
                                     '--outbox', str(args.outbox), '--watch'])
        current = fingerprint()
        if current != last:
            time.sleep(2)
            if fingerprint() != current:
                continue
            try:
                last = run(args.outbox)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                # Retry the same source after a transient failure; do not publish failed builds.
                print('CI watch will retry after failure: ' + str(exc), file=sys.stderr, flush=True)
                time.sleep(20)
        time.sleep(2)


if __name__ == '__main__':
    main()

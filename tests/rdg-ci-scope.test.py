#!/usr/bin/env python3
"""Conservative CI routing; isolated Git fixtures, no CI or runtime execution."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ci_scope_test', ROOT/'.github/scripts/rdg-ci-scope.py')
SCOPE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SCOPE)


def raw(path, status='M', before='100644', after='100644'):
    return (f':{before} {after} abcdef0 1234567 {status}\0'.encode() +
            path.encode() + b'\0')


class Classification(unittest.TestCase):
    def test_every_audited_document_content_change_uses_docs_checks(self):
        for name in SCOPE.DOCS_ONLY:
            with self.subTest(path=name):
                self.assertEqual(SCOPE.classify_diff(raw(name))[0], 'docs')

    def test_runtime_and_indirect_inputs_keep_full_gate(self):
        for name in ('tools/rdg-server.py', '.github/workflows/rdg-ci.yml',
                     'tests/fixture.md', 'docs/lenses/bootstrap/work.md',
                     'docs/handoffs/example/source.md', 'docs/DOCS-POLICY.json',
                     'docs/guides/RDG-OPERATIONS.md', 'docs/new-guide.md',
                     'deploy/rdg-server/README.md', 'readme.md'):
            with self.subTest(path=name):
                self.assertEqual(SCOPE.classify_diff(raw(name))[0], 'full')
        self.assertEqual(SCOPE.classify_diff(raw('README.md') + raw('tools/new.py'))[0], 'full')

    def test_deletions_additions_renames_and_file_modes_keep_full_gate(self):
        for status in ('A', 'D', 'T', 'R100', 'C100', 'U'):
            with self.subTest(status=status):
                self.assertEqual(SCOPE.classify_diff(raw('README.md', status))[0], 'full')
        for mode in ('120000', '100755', '160000', '000000'):
            self.assertEqual(SCOPE.classify_diff(raw('README.md', before=mode))[0], 'full')
            self.assertEqual(SCOPE.classify_diff(raw('README.md', after=mode))[0], 'full')

    def test_empty_malformed_oversized_and_non_utf8_diff_keep_full_gate(self):
        for data in (b'', b'bad', b'header\0', raw('README.md')[:-1],
                     raw('README.md').replace(b'README.md', b'\xff'),
                     b'x' * (SCOPE.MAX_DIFF_BYTES + 1)):
            self.assertEqual(SCOPE.classify_diff(data)[0], 'full')


class RepositoryEvents(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rdg-ci-scope-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Isolated CI fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.root/'README.md').write_text('Original\n')
        (self.root/'AGENTS.md').write_text('Original\n')
        self.base = self.commit()
        (self.root/'README.md').write_text('Documentation edit\n')
        self.head = self.commit()

    def git(self, *args):
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        return subprocess.check_output(['git', *args], cwd=self.root, env=env,
                                       stderr=subprocess.PIPE).decode().strip()

    def commit(self):
        self.git('add', '--all')
        self.git('commit', '-qm', 'Isolated fixture revision')
        return self.git('rev-parse', 'HEAD')

    def push(self, **extra):
        return dict(ref='refs/heads/main', before=self.base, after=self.head, **extra)

    def pr(self):
        return {'pull_request': {'base': {'ref': 'main', 'sha': self.base},
                                 'head': {'sha': self.head}}}

    def test_real_push_diff_selects_docs(self):
        result = SCOPE.select(self.root, 'push', self.push(), self.head)
        self.assertEqual(result['mode'], 'docs')
        self.assertEqual(result['base'], self.base)

    def test_unverified_push_and_checkout_keep_full_gate(self):
        changes = ({'before': '0'*40}, {'before': 'a'*40}, {'before': None},
                   {'after': self.base}, {'ref': 'refs/heads/task/test'}, {'deleted': True})
        for change in changes:
            with self.subTest(change=change):
                self.assertEqual(SCOPE.select(self.root, 'push', {**self.push(), **change}, self.head)['mode'], 'full')
        self.assertEqual(SCOPE.select(self.root, 'push', self.push(), self.base)['mode'], 'full')

    def test_pr_and_manual_event_scopes(self):
        self.assertEqual(SCOPE.select(self.root, 'pull_request', self.pr(), self.head)['mode'], 'docs')
        self.assertEqual(SCOPE.select(self.root, 'workflow_dispatch', {}, self.head)['mode'], 'full')
        for value in (None, {}, [], {'pull_request': None}):
            self.assertEqual(SCOPE.select(self.root, 'pull_request', value, self.head)['mode'], 'full')

    def test_merge_context_contains_exact_pr_head_and_latest_base(self):
        feature = self.head
        self.git('checkout', '-q', '-b', 'new-main', self.base)
        (self.root/'runtime.py').write_text('Already on main\n')
        base = self.commit()
        self.git('merge', '-q', '--no-ff', feature, '-m', 'Synthetic PR merge')
        merged = self.git('rev-parse', 'HEAD')
        event = {'pull_request': {'base': {'ref': 'main', 'sha': base},
                                  'head': {'sha': feature}}}
        self.assertEqual(SCOPE.select(self.root, 'pull_request', event, merged)['mode'], 'docs')
        event['pull_request']['head']['sha'] = 'b'*40
        self.assertEqual(SCOPE.select(self.root, 'pull_request', event, merged)['mode'], 'full')

    def test_actual_deletion_and_rename_keep_full_gate(self):
        (self.root/'AGENTS.md').unlink()
        deleted = self.commit()
        event = {**self.push(), 'after': deleted}
        self.assertEqual(SCOPE.select(self.root, 'push', event, deleted)['mode'], 'full')
        self.git('mv', 'README.md', 'other.md')
        renamed = self.commit()
        event = {**event, 'before': deleted, 'after': renamed}
        self.assertEqual(SCOPE.select(self.root, 'push', event, renamed)['mode'], 'full')

    def test_cli_outputs_scope_without_publishing_release(self):
        event_file = self.root/'event.json'
        event_file.write_text(json.dumps(self.push()))
        output = self.root/'actions-output'
        env = {'GITHUB_EVENT_PATH': str(event_file), 'GITHUB_EVENT_NAME': 'push',
               'GITHUB_SHA': self.head, 'GITHUB_OUTPUT': str(output),
               'GITHUB_STEP_SUMMARY': str(self.root/'summary')}
        self.assertEqual(SCOPE.main(env, self.root)['mode'], 'docs')
        self.assertEqual(output.read_text(), 'mode=docs\n')
        self.assertIn('no runtime release', (self.root/'summary').read_text())
        self.assertFalse((self.root/'ready.json').exists())
        event_file.write_text('{broken')
        self.assertEqual(SCOPE.main(env, self.root)['mode'], 'full')


class Workflow(unittest.TestCase):
    def test_required_job_runs_for_both_scopes_and_release_steps_require_full(self):
        text = (ROOT/'.github/workflows/rdg-ci.yml').read_text()
        self.assertEqual(text.count('branches: [main]'), 2)
        self.assertNotIn('paths-ignore:', text)
        self.assertNotIn('pull_request_target:', text)
        self.assertIn('  check-and-package:\n    runs-on:', text)
        self.assertIn("run: node --test tests/rdg-documentation.test.cjs", text)
        steps = text.split('      - ')[1:]
        for needle in ('Prepare isolated runtime', 'Isolated tests and frozen',
                       'Build runtime image', 'uses: actions/upload-artifact'):
            matched = [step for step in steps if needle in step]
            self.assertTrue(matched, needle)
            for step in matched:
                self.assertIn("steps.scope.outputs.mode == 'full'", step)
        routing = next(step for step in steps if 'name: CI routing contract tests' in step)
        self.assertNotIn('if:', routing)
        self.assertIn('run: python -B tests/rdg-ci-scope.test.py', routing)
        self.assertIn('run: python -B .github/scripts/rdg-ci-scope.py', text)


if __name__ == '__main__':
    unittest.main()

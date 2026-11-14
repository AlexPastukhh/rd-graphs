#!/usr/bin/env python3
"""Choose documentation checks or the full gate from a complete local Git diff."""
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
# Exact audited inputs only. In particular OPERATIONS supplies the runtime ZIP
# README; lenses, handoffs, fixtures, policy JSON and new paths stay on full CI.
DOCS_ONLY = frozenset((
    'README.md', 'AGENTS.md', 'BACKLOG-IMPROVEMENTS.md',
    'POTENTIAL-IMPROVEMENTS.md', 'docs/README.md',
    'docs/guides/RDG-CURRENT-STATE.md',
    'docs/guides/RDG-DEVELOPMENT-PLAN.md',
    'docs/guides/RDG-FUNCTIONS-AND-TESTS.md',
    'docs/guides/VIEWER-EXPLORER.md',
    'docs/guides/RDG-AGENT-BOOTSTRAP.md',
    'docs/guides/RDG-DECISION-V1-CONTRACT.md',
    'docs/use-cases/README.md', 'docs/use-cases/getting-started.md',
    'docs/use-cases/ai-work.md', 'docs/use-cases/development.md',
))
SHA = re.compile(r'[0-9a-f]{40}\Z')
MAX_DIFF_BYTES = 2 * 1024 * 1024


def git(root, *args):
    return subprocess.run(['git', *args], cwd=root, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=15).stdout


def classify_diff(raw):
    """Only regular-file content modifications of the allowlist use fast checks."""
    if not raw or len(raw) > MAX_DIFF_BYTES:
        return 'full', 'empty-or-oversized-diff'
    parts = raw.split(b'\0')
    if parts.pop() != b'' or len(parts) % 2:
        return 'full', 'invalid-diff'
    for header, name in zip(parts[::2], parts[1::2]):
        fields = header.split()
        if (len(fields) != 5 or fields[0] != b':100644' or
                fields[1] != b'100644' or fields[4] != b'M'):
            return 'full', 'non-content-change'
        try:
            path = name.decode('utf8')
        except UnicodeDecodeError:
            return 'full', 'invalid-path'
        if path not in DOCS_ONLY:
            return 'full', 'outside-documentation-allowlist'
    return 'docs', 'audited-documentation-only'


def select(root, event_name, event, expected_head):
    result = {'mode': 'full', 'reason': 'unverified-event'}
    try:
        if not isinstance(event, dict) or not SHA.fullmatch(expected_head or ''):
            return result
        actual = git(root, 'rev-parse', 'HEAD').decode().strip()
        if actual != expected_head:
            return {**result, 'reason': 'checkout-head-mismatch'}
        if event_name == 'push':
            if (event.get('ref') != 'refs/heads/main' or event.get('deleted') or
                    event.get('after') != actual):
                return result
            base = event.get('before')
        elif event_name == 'pull_request':
            pr = event['pull_request']
            if pr['base']['ref'] != 'main':
                return result
            base = pr['base']['sha']
            source = pr['head']['sha']
            if not isinstance(source, str) or not SHA.fullmatch(source):
                return result
            # checkout uses GitHub's PR merge context, retaining integration
            # coverage. It must contain this exact PR head and base.
            git(root, 'merge-base', '--is-ancestor', source, actual)
        else:
            return {**result, 'reason': 'full-event'}
        if not isinstance(base, str) or not SHA.fullmatch(base) or base == '0' * 40:
            return {**result, 'reason': 'unverified-base'}
        git(root, 'merge-base', '--is-ancestor', base, actual)
        raw = git(root, 'diff', '--raw', '-z', '--no-renames',
                  '--no-ext-diff', '--no-textconv', base, actual, '--')
        mode, reason = classify_diff(raw)
        return {'mode': mode, 'reason': reason, 'base': base, 'head': actual}
    except (OSError, ValueError, TypeError, KeyError, AttributeError,
            subprocess.SubprocessError):
        return {**result, 'reason': 'diff-unavailable'}


def main(environ=None, root=ROOT):
    env = os.environ if environ is None else environ
    try:
        event = json.loads(Path(env['GITHUB_EVENT_PATH']).read_text())
    except (KeyError, OSError, ValueError):
        event = None
    result = select(root, env.get('GITHUB_EVENT_NAME'), event, env.get('GITHUB_SHA'))
    print(json.dumps(result, sort_keys=True))
    if env.get('GITHUB_OUTPUT'):
        with Path(env['GITHUB_OUTPUT']).open('a') as stream:
            stream.write('mode=' + result['mode'] + '\n')
    if env.get('GITHUB_STEP_SUMMARY'):
        with Path(env['GITHUB_STEP_SUMMARY']).open('a') as stream:
            stream.write('Validation scope: **' + result['mode'] + '** (' +
                         result['reason'] + ').\n')
            if result['mode'] == 'docs':
                stream.write('Documentation checks only; no runtime release or image is produced.\n')
    return result


if __name__ == '__main__':
    main()

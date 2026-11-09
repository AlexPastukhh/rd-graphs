#!/usr/bin/env python3
"""Freeze a versioned RDG runtime and operator files; no owners or credentials."""
import argparse
import hashlib
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build(output, build_id=None):
    output = Path(output)
    if output.exists() or output.suffix.lower() != '.zip':
        raise ValueError('CHOOSE_NEW_ZIP_OUTPUT')
    preview = SourceFileLoader('server_runtime_inventory', str(ROOT / 'tools/rdg-preview-package.py')).load_module()
    sources = [Path('tools') / (name + '.py') for name in preview.PYTHON_FILES if name != 'rdg-preview']
    sources += [Path('tools') / name for name in ('rdg-server.py', 'rdg_server_entry.py',
        'rdg-remote-client.py', 'rdg-gateway.py', 'rdg_gateway_entry.py', 'rdg-server-setup.py',
        'requirements-server.txt', 'rd-graph-viewer.user.js',
        'rdg-layout-cli.cjs', 'rdg-layout-core.js', 'rdg-visual-projection.js')]
    # Lens definitions are RDG FileStore data, not executable server inputs.
    # Agent/standalone preview fixtures keep their own source definitions.
    sources += sorted(p.relative_to(ROOT) for p in (ROOT / 'tools/contracts').glob('*.json'))
    payload = {}
    for relative in sources:
        source = ROOT / relative
        if not source.is_file() or source.is_symlink():
            raise ValueError('RUNTIME_SOURCE_REQUIRED:' + str(relative))
        payload['runtime/' + relative.as_posix()] = source.read_bytes()
    directory = ROOT / 'deploy/rdg-server'
    for name in ('Dockerfile', 'compose.yaml', 'compose.local.yaml', 'compose.https.yaml',
                 'Caddyfile', 'Caddyfile.local', '.dockerignore', '.env.example',
                 'Start-RDG.ps1', 'Stop-RDG.ps1', 'Update-RDG.ps1'):
        payload[name] = (directory / name).read_bytes()
    ops = (ROOT / 'docs/guides/RDG-OPERATIONS.md').read_text()
    start, end = '<!-- RDG SERVER PACKAGE BEGIN -->', '<!-- RDG SERVER PACKAGE END -->'
    if ops.count(start) != 1 or ops.count(end) != 1:
        raise ValueError('SERVER_OPERATOR_GUIDE_REQUIRED')
    payload['README.md'] = (ops.split(start, 1)[1].split(end, 1)[0].strip() + '\n').encode()
    content_sha = hashlib.sha256(json.dumps({name: hashlib.sha256(raw).hexdigest()
        for name, raw in sorted(payload.items())}, sort_keys=True).encode()).hexdigest()
    build_id = build_id or 'dev-' + content_sha[:20]
    if not isinstance(build_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,110}', build_id):
        raise ValueError('BUILD_ID_INVALID')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    identity = {'buildId': build_id, 'contentSHA256': content_sha, 'repositoryHead': head}
    payload['runtime/RDG-BUILD.json'] = (json.dumps(identity, indent=2) + '\n').encode()
    manifest = {'schemaVersion': 1, 'kind': 'rdg-personal-server-package',
        'serverBuild': build_id, 'imageTag': build_id, 'repositoryHead': head,
        'workingTreeSnapshot': True, 'includesUserData': False,
        'files': {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(payload.items())}}
    payload['BUILD.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(payload.items()):
            archive.writestr('RDG-Server/' + name, raw)
    return {'file': str(output), 'bytes': output.stat().st_size,
            'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'files': len(payload),
            'buildId': build_id, 'contentSHA256': content_sha}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--build-id')
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.build_id)))

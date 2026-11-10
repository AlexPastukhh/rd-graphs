"""Deterministic R7 source-only package builder; no Docker/network/secrets.

The package's bytes are pinned separately in Build-R7-Windows-ImageOnly.ps1.
Run only in the Fortis Repo *development workspace* to prepare a source ZIP.
"""
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_STORED
import sys

ROOT = Path(__file__).resolve().parents[2]
DEST = Path('/workspace/repo/Workfiles/fortis-r7-unified-source-review-v2-20261101.zip')
NAMES = (
    'fortis_approvals/__init__.py',
    'fortis_approvals/a3_server.py',
    'fortis_approvals/core.py',
    'fortis_approvals/deploy/Dockerfile-R7-Unified-Read-Ask-Candidate',
    'fortis_approvals/owner_auth.py',
    'fortis_approvals/owner_portal.py',
    'fortis_approvals/r5_read_candidate.py',
    'fortis_approvals/r5_read_server.py',
    'fortis_approvals/r7_unified_candidate.py',
    'fortis_approvals/r7_unified_server.py',
    'fortis_approvals/repo_action_contract.py',
    'fortis_approvals/repo_ingress.py',
    'fortis_approvals/requirements-owner.txt',
    'fortis_approvals/server.py',
    'fortis_approvals/sonar.py',
    'fortis_approvals/sonar_inventory.py',
    'fortis_approvals/sonar_read.py',
    'fortis_approvals/static/app.js',
    'fortis_approvals/static/index.html',
    'fortis_approvals/static/style.css',
)


def _info(name):
    entry = ZipInfo(name, date_time=(2026, 11, 1, 0, 0, 0))
    entry.compress_type = ZIP_STORED
    entry.external_attr = 0o100644 << 16
    return entry


def main():
    if len(sys.argv) != 1:
        raise SystemExit('R7_PACKAGE_NO_ARGUMENTS')
    if DEST.exists():
        raise SystemExit('R7_REVIEW_ZIP_ALREADY_EXISTS_NO_OVERWRITE')
    if len(NAMES) != len(set(NAMES)) or len(NAMES) != 20:
        raise SystemExit('R7_REVIEW_NAMES_UNEXPECTED')
    if not DEST.parent.is_dir():
        raise SystemExit('R7_WORKFILES_DIR_MISSING')
    manifest = []
    sources = {}
    for name in NAMES:
        source = ROOT / name
        if (not source.is_file() or source.is_symlink() or
                source.resolve() != (ROOT/name).resolve()):
            raise SystemExit('R7_SOURCE_MISSING_OR_SYMLINK')
        data = source.read_bytes()
        if not data or len(data) > 1048576:
            raise SystemExit('R7_REVIEW_SOURCE_SIZE_INVALID')
        sources[name] = data
        manifest.append(sha256(data).hexdigest() + '  ' + name + '\n')
    manifest_bytes = ''.join(manifest).encode('ascii')
    with ZipFile(DEST, 'x', compression=ZIP_STORED) as output:
        output.writestr(_info('SOURCE-MANIFEST.sha256'),manifest_bytes)
        for name in NAMES:
            output.writestr(_info(name),sources[name])
    print('FORTIS_R7_ZIP_FILE_COUNT='+str(len(NAMES)))
    print('FORTIS_R7_MANIFEST_SHA256='+sha256(manifest_bytes).hexdigest())
    print('FORTIS_R7_DOCKERFILE_SHA256='+sha256(
        sources['fortis_approvals/deploy/Dockerfile-R7-Unified-Read-Ask-Candidate']).hexdigest())
    print('FORTIS_R7_ZIP_SHA256='+sha256(DEST.read_bytes()).hexdigest())
    print('FORTIS_R7_ZIP_BYTES='+str(DEST.stat().st_size))


if __name__=='__main__':
    main()

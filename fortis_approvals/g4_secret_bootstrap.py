"""One-shot offline G4 token provisioning from stdin into a private volume.

Never logs tokens, reads from argv/env, or overwrites an existing credential.
Run in a temporary no-network Docker container as uid 10001, not in Repo.
"""
import os
from pathlib import Path
import stat
import sys
import tempfile

DEST = Path('/run/g4-token/private/sonar_token')


def provision(*, stream=None, target=DEST):
    stream = stream or sys.stdin
    # Line-reading is bounded; no token is accepted as CLI args or environment.
    value = stream.readline(4098).rstrip('\r\n')
    if not 12 <= len(value) <= 4096 or any(c.isspace() for c in value):
        raise ValueError('G4_TOKEN_INVALID')
    root = target.parent
    info = root.stat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or (info.st_mode & 0o077) or target.is_symlink()):
        raise ValueError('G4_SECRET_VOLUME_NOT_PRIVATE')
    if target.exists():
        raise ValueError('G4_TOKEN_ALREADY_PROVISIONED')
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix='.new-g4-token-', dir=str(root))
        with os.fdopen(fd, 'wb') as out:
            out.write(value.encode('utf-8'))
            out.flush()
            os.fsync(out.fileno())
        os.chmod(tmp, 0o600)
        # Atomic link refuses an existing target rather than replacing it.
        os.link(tmp, target, follow_symlinks=False)
        return True
    finally:
        if tmp is not None:
            os.unlink(tmp)


def main():
    try:
        provision()
        print('G4_TOKEN_PROVISIONED_PRIVATE_VOLUME', flush=True)
        return 0
    except (OSError, ValueError):
        # Never surface secret bytes, paths, or untrusted upstream messages.
        print('G4_TOKEN_PROVISION_DENIED_OR_ALREADY_PRESENT', file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())

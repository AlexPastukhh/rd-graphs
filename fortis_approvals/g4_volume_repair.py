"""Offline G4-only volume *subdirectory* initializer/verifier.

Do not chmod/chown the named volume root: Windows Docker Desktop reported
UID 0/mode 0755 across mounts even after root chown/chmod exited zero.
This module creates /state/private or /run/g4-token/private ONLY and never
reads credential contents, imports owner state or changes other volumes.
"""
import argparse
import os
from pathlib import Path
import stat
import sys
import tempfile

ROOTS = {'state': Path('/state'), 'token': Path('/run/g4-token')}
OWNER_UID = 10001


def _private(root):
    if root.is_symlink() or not root.is_dir():
        raise ValueError('G4_VOLUME_MOUNT_INVALID')
    return root / 'private'


def initialize(root):
    if os.geteuid() != 0:
        raise ValueError('G4_PRIVILEGED_BOOTSTRAP_REQUIRED')
    private = _private(root)
    if private.is_symlink():
        raise ValueError('G4_PRIVATE_SYMLINK_DENIED')
    if private.exists():
        if not private.is_dir():
            raise ValueError('G4_PRIVATE_INVALID')
        verify_metadata(private)
        return 'ALREADY_READY'
    # Refuse to adopt a volume with unknown earlier content or an existing
    # G2 database. Never remove/reformat any existing file/volume.
    if any(root.iterdir()):
        raise ValueError('G4_VOLUME_NOT_EMPTY_UNKNOWN_CONTENT')
    private.mkdir(mode=0o700)
    os.chown(private, OWNER_UID, OWNER_UID)
    os.chmod(private, 0o700)
    verify_metadata(private)
    return 'CREATED'


def verify_metadata(private):
    if private.is_symlink():
        raise ValueError('G4_PRIVATE_SYMLINK_DENIED')
    info = private.stat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != OWNER_UID or
            info.st_gid != OWNER_UID or stat.S_IMODE(info.st_mode) != 0o700):
        raise ValueError('G4_PRIVATE_PERMISSIONS_INVALID')


def check_write(root):
    if os.geteuid() != OWNER_UID:
        raise ValueError('G4_UNPRIVILEGED_VERIFICATION_REQUIRED')
    private = _private(root)
    verify_metadata(private)
    temporary = link = None
    try:
        fd, temporary = tempfile.mkstemp(prefix='.g4-volume-selftest-', dir=private)
        os.close(fd)
        link = temporary + '.link'
        os.link(temporary, link)
    finally:
        for name in (link, temporary):
            if name is not None and os.path.lexists(name):
                os.unlink(name)
    return 'WRITE_AND_LINK_OK'


def _mounted(root):
    # os.path.ismount() can miss Linux bind mounts on a matching filesystem.
    # Docker exposes every mounted volume in /proc/self/mountinfo instead.
    try:
        with open('/proc/self/mountinfo', encoding='utf-8') as mounts:
            return any(len(parts) > 4 and parts[4] == str(root)
                       for parts in (line.split() for line in mounts))
    except OSError:
        return False


def main(argv=None):
    cli = argparse.ArgumentParser(description='G4 named-volume private directory check')
    cli.add_argument('action', choices=('initialize', 'verify'))
    cli.add_argument('kind', choices=sorted(ROOTS))
    args = cli.parse_args(argv)
    root = ROOTS[args.kind]
    try:
        if not _mounted(root):
            raise ValueError('G4_REQUIRED_NAMED_VOLUME_NOT_MOUNTED')
        if args.action == 'initialize':
            result = initialize(root)
        else:
            result = check_write(root)
        print('G4_PRIVATE_' + args.kind.upper() + '_' + result, flush=True)
        return 0
    except (OSError, ValueError):
        print('G4_PRIVATE_' + args.kind.upper() + '_CHECK_FAILED', file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())

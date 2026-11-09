#!/usr/bin/env python3
"""POSIX transaction IO boundary. No Graph/Plan semantics or token handling.

All compatible writers share a reference barrier before their owner locks.
Read/preflight never creates a barrier. Atomic publication includes file and
parent-directory fsync; native Windows write support is explicit, not assumed.
"""
from contextlib import contextmanager
import errno
import hashlib
import json
import os
from pathlib import Path
import tempfile


def require(condition, code):
    if not condition:raise ValueError('TX_IO_' + code)


def sha256(value):return hashlib.sha256(value).hexdigest()


def safe_path(root, relative, allow_metadata=False):
    root = Path(root).absolute()
    require(isinstance(relative, str) and bool(relative) and not relative.startswith('/') and
            '\\' not in relative and ':' not in relative and '\x00' not in relative, 'RELATIVE_PATH_REQUIRED')
    parts = relative.split('/')
    require(all(part and part not in ('.', '..') for part in parts), 'PATH_COMPONENT')
    require(allow_metadata or not any(part.startswith('.') for part in parts), 'PRIVATE_PATH')
    path = root
    require(not root.is_symlink(), 'SYMLINK_ROOT')
    for part in parts:
        path /= part
        require(not path.is_symlink(), 'SYMLINK_PATH')
    require(path.resolve().is_relative_to(root.resolve()), 'PATH_ESCAPE')
    return path


def sync_dir(path):
    require(os.name == 'posix' and hasattr(os, 'O_DIRECTORY'), 'NATIVE_WRITE_BACKEND_UNSUPPORTED')
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def mkdirs(path):
    path = Path(path)
    require(not path.is_symlink(), 'SYMLINK_DIRECTORY')
    missing = [];current = path
    while not current.exists():missing.append(current);current = current.parent
    require(current.is_dir(), 'PARENT_NOT_DIRECTORY')
    for item in reversed(missing):
        try:item.mkdir()
        except FileExistsError:require(item.is_dir() and not item.is_symlink(), 'DIRECTORY_RACE')
        sync_dir(item);sync_dir(item.parent)


def atomic_bytes(path, payload):
    require(isinstance(payload, bytes), 'BYTES_REQUIRED')
    path = Path(path);mkdirs(path.parent)
    require(not path.is_symlink(), 'SYMLINK_FILE')
    fd, temporary = tempfile.mkstemp(prefix='.rdg-write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary, path);sync_dir(path.parent)
        require(path.read_bytes() == payload, 'WRITE_READBACK_MISMATCH')
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def immutable_bytes(path, payload):
    path = Path(path)
    if path.exists():
        require(path.is_file() and not path.is_symlink() and path.read_bytes() == payload, 'IMMUTABLE_CONTENT_CONFLICT')
    else:atomic_bytes(path, payload)


def file_sha(path):
    path = Path(path)
    require(not path.is_symlink(), 'SYMLINK_FILE')
    return sha256(path.read_bytes()) if path.is_file() else None


@contextmanager
def reference_lock(root, exclusive, create=True):
    root = Path(root).absolute()
    require(root.is_dir() and not root.is_symlink(), 'COORDINATION_ROOT_REQUIRED')
    path = safe_path(root, '.rdg-reference.lock', True)
    if not path.exists() and not create:
        yield
        return
    require(os.name == 'posix', 'NATIVE_WRITE_BACKEND_UNSUPPORTED')
    import fcntl
    flags = os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
    if create:flags |= os.O_CREAT
    try:fd = os.open(path, flags, 0o600)
    except FileNotFoundError:
        if not create:
            yield
            return
        raise
    with os.fdopen(fd, 'a+b') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:yield
        finally:fcntl.flock(stream, fcntl.LOCK_UN)

def legacy_owner_route(path):
    marker=Path(path).with_name(Path(path).name+'.rdg-migration.json')
    if not marker.exists():return None
    require(not marker.is_symlink() and marker.is_file(),'UNSAFE_LEGACY_ROUTE')
    value=json.loads(marker.read_bytes())
    require(value.get('schemaVersion')==1 and value.get('kind')=='legacyOwnerRoute' and
            value.get('state') in ('switching','committed') and
            all(isinstance(value.get(k),str) and value[k] for k in ('transactionId','packageId','namespaceId','requestSHA256')),
            'LEGACY_ROUTE_INVALID')
    return value


def require_current_legacy(path):
    route=legacy_owner_route(path)
    if route:raise ValueError('LEGACY_OWNER_MIGRATED: packageId='+route['packageId']+'; state='+route['state'])

def portable_container(path,root):
    """A generation inside a package is a snapshot, never a legacy owner."""
    root=Path(root).absolute();path=Path(path).absolute()
    for directory in (path.parent,*path.parent.parents):
        if not directory.is_relative_to(root):break
        marker=directory/'.rdg/package.json';manifest=directory/'package.json'
        require(not marker.is_symlink() and not manifest.is_symlink(),'SYMLINK_PACKAGE_METADATA')
        if marker.is_file():return directory
        if manifest.is_file():
            value=json.loads(manifest.read_bytes())
            if isinstance(value,dict) and value.get('kind')=='rdgGraphPackage':return directory
    return None

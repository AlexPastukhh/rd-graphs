#!/usr/bin/env python3
"""Test-only POSIX handles reproducing Windows preview read serialization."""
from contextlib import contextmanager
from importlib.machinery import SourceFileLoader
from pathlib import Path
import errno
import fcntl
import os
import sys

def serialized_io(io):
    @contextmanager
    def reference_lock(root, exclusive, create=True):
        root=Path(root).absolute()
        io.require(root.is_dir() and not root.is_symlink(),'COORDINATION_ROOT_REQUIRED')
        path=io.safe_path(root,'.rdg-reference.lock',True)
        if not path.exists() and not create:
            yield
            return
        flags=os.O_RDWR | getattr(os,'O_NOFOLLOW',0) | (os.O_CREAT if create else 0)
        with os.fdopen(os.open(path,flags,0o600),'a+b') as stream:
            try:fcntl.flock(stream,fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise PermissionError(errno.EACCES,'Serialized preview handles contend') from exc
            try:yield
            finally:fcntl.flock(stream,fcntl.LOCK_UN)
    io.reference_lock=reference_lock
    return io

def main():
    runtime=Path(sys.argv.pop(1)).resolve()
    preview=SourceFileLoader('serialized_preview_runtime',str(runtime)).load_module()
    original=preview.preview_io
    preview.preview_io=lambda:serialized_io(original())
    preview.main()

if __name__=='__main__':main()

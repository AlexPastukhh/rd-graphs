#!/usr/bin/env python3
"""Windows byte-range locks for the explicitly selected preview runtime.

Shared requests serialize as exclusive locks. This trades concurrency for the
same exclusion rule; it does not provide directory flush or OS isolation.
"""
import errno
import os
import time
import msvcrt

LOCK_SH, LOCK_EX, LOCK_UN = 1, 2, 8

def flock(stream, operation):
    fd = stream if isinstance(stream, int) else stream.fileno()
    position = os.lseek(fd, 0, os.SEEK_CUR)
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        if operation == LOCK_UN:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            return
        if operation not in (LOCK_SH, LOCK_EX):
            raise ValueError("RDG_WINDOWS_LOCK_OPERATION")
        until = time.monotonic() + 30
        while True:
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                return
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK) or time.monotonic() >= until:
                    raise
                time.sleep(0.02)
    finally:
        os.lseek(fd, position, os.SEEK_SET)

#!/usr/bin/env python3
"""Crash-recoverable incremental journal for the disposable RDG teaching example.

The public journal path stays a compatible full JSON checkpoint on exit.
Durable individual updates are written to a sidecar .wal between checkpoints;
do not use this helper for RDG's actual transaction store.
"""
import json
import os
from pathlib import Path


class Journal:
    def __init__(self, path, initial_state):
        self.path = Path(path)
        self.wal = Path(str(self.path) + '.wal')
        if self.path.is_file():
            try:
                content = self.path.read_text(encoding='utf-8-sig')
            except UnicodeDecodeError:
                # Pre-WAL operator journals used the local text encoding on
                # Windows. Continue to read those; always export new UTF-8.
                import locale
                content = self.path.read_text(encoding=locale.getpreferredencoding(False))
            self.state = json.loads(content)
        else:
            self.state = initial_state
        self.sequence = self.state.pop('_journalSeq', 0)
        if self.wal.is_file():
            self._replay()

    def _replay(self):
        content = self.wal.read_bytes()
        valid_end = content.rfind(b'\n') + 1
        if valid_end < len(content):
            # A process may have stopped between appending a record and its
            # trailing newline. An incomplete record was never durable.
            with self.wal.open('r+b') as stream:
                stream.truncate(valid_end)
                stream.flush()
                os.fsync(stream.fileno())
        for raw in content[:valid_end].splitlines():
            record = json.loads(raw)
            seq = record['seq']
            if seq <= self.sequence:
                continue  # Checkpoint published, old WAL not yet removed.
            if seq != self.sequence + 1:
                raise ValueError('EXAMPLE_JOURNAL_SEQUENCE_GAP')
            self.state.update(record['meta'])
            if 'key' in record:
                self.state['operations'][record['key']] = record['operation']
            self.sequence = seq

    def _sync_parent(self):
        # POSIX directory durability: the WAL name and the published JSON
        # replacement must survive a machine-level crash before WAL removal.
        if os.name != 'posix':
            return
        fd = os.open(self.path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def append(self, key=None):
        """Persist exactly one changed operation plus small root metadata.

        The caller updates self.state before appending. fsync makes each
        accepted transactionId and recovery intent durable before continuing.
        """
        if key is not None and key not in self.state['operations']:
            raise KeyError(key)
        record = {
            'seq': self.sequence + 1,
            'meta': {k: v for k, v in self.state.items() if k != 'operations'}
        }
        if key is not None:
            record.update(key=key, operation=self.state['operations'][key])
        encoded = (json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        first_record = not self.wal.exists()
        with self.wal.open('ab') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if first_record:
            self._sync_parent()
        self.sequence += 1

    def checkpoint(self):
        """Atomically export legacy-compatible full JSON at run exit.

        A crash after replacement but before WAL removal is safe: the next
        reader ignores WAL records whose sequence is already checkpointed.
        """
        if not self.wal.is_file():
            return
        content = {**self.state, '_journalSeq': self.sequence}
        encoded = json.dumps(content, ensure_ascii=False, indent=2) + '\n'
        temporary = self.path.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.path)
        self._sync_parent()  # Never discard WAL before the JSON is durable.
        self.wal.unlink()
        self._sync_parent()

"""Persistent synthetic typed adapter, never connected to RDG/Sonar/Windows."""
import json
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from .core import Denied, Stale, canonical


class SyntheticAdapter:
    OPERATIONS = {'set_free', 'set_ask', 'set_deny'}

    def __init__(self, database):
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fail_after_commit_once = False  # crash/timeout test hook
        with self._db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS objects (
                id TEXT PRIMARY KEY, version INTEGER NOT NULL, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS receipts (
                id TEXT PRIMARY KEY, result TEXT NOT NULL);''')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db:
                yield db
        finally:
            db.close()

    def seed(self, key, value, version=0):
        with self._db() as db:
            db.execute('INSERT INTO objects(id,version,value) VALUES(?,?,?)',
                       (key, version, value))

    def get(self, key):
        with self._db() as db:
            row = db.execute('SELECT version,value FROM objects WHERE id=?', (key,)).fetchone()
            return dict(row) if row else None

    def prepare(self, request):
        if (request['operation'] not in self.OPERATIONS or
            set(request['params']) != {'value'} or
            not isinstance(request['params']['value'], str) or
            len(request['params']['value']) > 1000):
            raise Denied('SYNTHETIC_OPERATION_DENIED')
        current = self.get(request['target'])
        if not current or current['version'] != request['expectedVersion']:
            raise Stale('TARGET_VERSION_CHANGED')
        return {'before': current, 'after': {'value': request['params']['value'],
                'version': current['version'] + 1}, 'target': request['target']}

    def apply(self, request):
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            prev = db.execute('SELECT result FROM receipts WHERE id=?',
                              (request['requestId'],)).fetchone()
            if prev:
                return json.loads(prev['result'])
            current = db.execute('SELECT version FROM objects WHERE id=?',
                                 (request['target'],)).fetchone()
            if not current or current['version'] != request['expectedVersion']:
                raise Stale('TARGET_VERSION_CHANGED')
            new_version = current['version'] + 1
            db.execute('UPDATE objects SET version=?, value=? WHERE id=?',
                       (new_version, request['params']['value'], request['target']))
            result = {'requestId': request['requestId'], 'target': request['target'],
                      'value': request['params']['value'], 'version': new_version}
            db.execute('INSERT INTO receipts(id,result) VALUES(?,?)',
                       (request['requestId'], canonical(result)))
        if self.fail_after_commit_once:
            self.fail_after_commit_once = False
            raise TimeoutError('synthetic response lost AFTER durable commit')
        return result

    def receipt(self, request_id):
        with self._db() as db:
            row = db.execute('SELECT result FROM receipts WHERE id=?', (request_id,)).fetchone()
            return json.loads(row['result']) if row else None

    def confirm(self, request_id, result):
        return (isinstance(result, dict) and result.get('requestId') == request_id and
                self.receipt(request_id) == result)

"""Bounded process-local cache for verified, deterministic read projections.

Only bytes are retained. JSON decode on hit prevents response mutation leaks;
there is no persistent store, global cache, or security decision here.
"""
from collections import OrderedDict
import json
from threading import RLock


class ProjectionCache:
    def __init__(self, max_entries=8, max_bytes=12 * 1024 * 1024):
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self._entries = OrderedDict()
        self._bytes = 0
        self._lock = RLock()

    @staticmethod
    def encode(value):
        return json.dumps(value, ensure_ascii=False, allow_nan=False,
                          sort_keys=True, separators=(',', ':')).encode('utf-8')

    def get(self, key):
        with self._lock:
            raw = self._entries.get(key)
            if raw is None:
                return None
            self._entries.move_to_end(key)
            return json.loads(raw)

    def put(self, key, value):
        raw = self.encode(value)
        if len(raw) > self.max_bytes or self.max_entries < 1:
            return
        with self._lock:
            previous = self._entries.pop(key, None)
            if previous is not None:
                self._bytes -= len(previous)
            self._entries[key] = raw
            self._bytes += len(raw)
            while len(self._entries) > self.max_entries or self._bytes > self.max_bytes:
                _, removed = self._entries.popitem(last=False)
                self._bytes -= len(removed)

    def __len__(self):
        with self._lock:
            return len(self._entries)

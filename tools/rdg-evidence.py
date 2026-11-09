"""Verify file pins for Graph confirmation at the authorized writer boundary."""
import copy
import hashlib
from pathlib import Path
import re


def verify(root, entries, protected=(), prefix='GRAPH_'):
    def require(ok, code):
        if not ok: raise ValueError(prefix+code)
    root=Path(root).resolve()
    require(isinstance(entries,list) and bool(entries),'FILE_EVIDENCE_REQUIRED')
    excluded={Path(p).resolve() for p in protected if p}
    checked=[]
    for entry in entries:
        require(isinstance(entry,dict) and set(entry)=={'path','sha256'},'EVIDENCE_SCHEMA')
        name=entry['path']
        require(isinstance(name,str) and bool(name) and not Path(name).is_absolute() and
                all(p not in ('.','..') and not p.startswith('.') for p in Path(name).parts),'EVIDENCE_PATH')
        path=root/name
        require(path.resolve().is_relative_to(root) and path.is_file() and
                not any(p.is_symlink() for p in [path,*path.parents]) and path.resolve() not in excluded,
                'EVIDENCE_FILE_UNSAFE')
        require(isinstance(entry['sha256'],str) and re.fullmatch('[a-f0-9]{64}',entry['sha256']) and
                hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256'],'EVIDENCE_CHANGED_OR_HASH_INVALID')
        checked.append(copy.deepcopy(entry))
    return checked

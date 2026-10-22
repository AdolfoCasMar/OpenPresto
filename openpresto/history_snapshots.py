"""Validated in-memory history with shared immutable large strings.

These snapshots are internal only. Portable project files still use storage JSON.
Mutable containers are rebuilt on every restoration; no global cache is retained.
"""
from dataclasses import dataclass, field
import json
from .storage import to_dict, from_dict, loads

_THRESHOLD = 16 * 1024


@dataclass(frozen=True, slots=True)
class Snapshot:
    payload: str = field(repr=False)
    bindings: tuple = field(repr=False)
    context: object = field(default=None, compare=False, repr=False)


def capture_snapshot(budget):
    bindings = []
    def detach(value, path):
        if isinstance(value, str) and len(value) >= _THRESHOLD:
            bindings.append((path, value))
            return None
        if isinstance(value, dict):
            return {key: detach(value[key], path + (key,)) for key in sorted(value)}
        if isinstance(value, list):
            return [detach(item, path + (index,)) for index, item in enumerate(value)]
        return value
    document = detach(to_dict(budget), ())
    return Snapshot(json.dumps(document, ensure_ascii=False, sort_keys=True,
                               separators=(',', ':'), allow_nan=False), tuple(bindings))


def restore_snapshot(snapshot):
    if isinstance(snapshot, str):
        return loads(snapshot)
    if not isinstance(snapshot, Snapshot):
        raise TypeError('Invalid internal project snapshot')
    document = json.loads(snapshot.payload)
    for path, value in snapshot.bindings:
        target = document
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    return from_dict(document)

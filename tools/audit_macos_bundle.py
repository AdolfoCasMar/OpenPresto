"""Check actual Mach-O minimum versions, including every universal slice.

This is a static prerequisite check, not a substitute for running on the target OS.
"""
from pathlib import Path
import struct


def version(value):
    return (value >> 16, (value >> 8) & 255, value & 255)


def slices(data):
    if data[:4] in (b'\xca\xfe\xba\xbe', b'\xca\xfe\xba\xbf'):
        wide = data[:4] == b'\xca\xfe\xba\xbf'
        count = struct.unpack_from('>I', data, 4)[0]
        if count > 64:
            raise ValueError('Invalid universal binary')
        for i in range(count):
            fmt = '>IIQQII' if wide else '>IIIII'
            row = struct.unpack_from(fmt, data, 8 + i * struct.calcsize(fmt))
            offset, size = row[2:4]
            if offset + size > len(data):
                raise ValueError('Truncated universal binary')
            yield from slices(data[offset:offset + size])
    elif data[:4] == b'\xcf\xfa\xed\xfe':
        cpu = struct.unpack_from('<I', data, 4)[0]
        count, command_bytes = struct.unpack_from('<II', data, 16)
        end = 32 + command_bytes
        if end > len(data):
            raise ValueError('Truncated load commands')
        pos = 32
        minimum = None
        for _ in range(count):
            cmd, size = struct.unpack_from('<II', data, pos)
            if size < 8 or pos + size > end:
                raise ValueError('Invalid load command')
            if cmd == 0x32:
                if struct.unpack_from('<I', data, pos + 8)[0] != 1:
                    raise ValueError('Non-macOS build platform')
                minimum = version(struct.unpack_from('<I', data, pos + 12)[0])
            elif cmd == 0x24:
                minimum = version(struct.unpack_from('<I', data, pos + 8)[0])
            pos += size
        yield cpu, minimum


def audit(bundle, maximum, cpu):
    target = tuple(int(x) for x in maximum.split('.'))
    target = (target + (0, 0, 0))[:3]
    errors, binaries = [], []
    for path in sorted(Path(bundle).rglob('*')):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open('rb') as stream:
            magic = stream.read(4)
        if magic not in (b'\xcf\xfa\xed\xfe', b'\xca\xfe\xba\xbe', b'\xca\xfe\xba\xbf'):
            continue
        name = str(path.relative_to(bundle))
        try:
            entries = [minimum for arch, minimum in slices(path.read_bytes()) if arch == cpu]
            if not entries or any(v is None or v > target for v in entries):
                errors.append(name + ': missing target architecture or unsupported minimum macOS')
            binaries.append({'file': name, 'minimum_versions': entries})
        except (ValueError, struct.error) as exc:
            errors.append(name + ': ' + str(exc))
    if not binaries:
        errors.append('No Mach-O binaries found')
    return {'target': maximum, 'binaries': binaries, 'errors': errors}

import struct
import tempfile
import unittest
from pathlib import Path
from tools.audit_macos_bundle import audit, slices


def binary(minimum, cpu=0x01000007):
    return struct.pack('<8I', 0xfeedfacf, cpu, 3, 2, 1, 24, 0, 0) + struct.pack('<6I', 0x32, 24, 1, minimum, minimum, 0)


class MacBundleAuditTests(unittest.TestCase):
    def test_checks_minimum_and_architecture(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'binary'
            path.write_bytes(binary(0x000a0f00))
            self.assertFalse(audit(folder, '10.15', 0x01000007)['errors'])
            path.write_bytes(binary(0x000d0000))
            self.assertTrue(audit(folder, '10.15', 0x01000007)['errors'])
            path.write_bytes(binary(0x000b0000, 0x0100000c))
            self.assertTrue(audit(folder, '10.15', 0x01000007)['errors'])

    def test_universal_slices_are_read_separately(self):
        intel, arm = binary(0x000a0f00), binary(0x000b0000, 0x0100000c)
        header = struct.pack('>II', 0xcafebabe, 2)
        header += struct.pack('>5I', 0x01000007, 3, 48, len(intel), 0)
        header += struct.pack('>5I', 0x0100000c, 0, 48 + len(intel), len(arm), 0)
        self.assertEqual(list(slices(header + intel + arm)), [(0x01000007, (10, 15, 0)), (0x0100000c, (11, 0, 0))])

    def test_truncated_binary_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'binary').write_bytes(binary(0x000a0f00)[:-1])
            self.assertTrue(audit(folder, '10.15', 0x01000007)['errors'])

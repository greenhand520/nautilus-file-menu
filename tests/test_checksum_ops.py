import unittest

from modules.checksum_ops import ChecksumOps


class ChecksumOpsTests(unittest.TestCase):
    def test_get_available_algorithms_filters_invalid(self):
        ops = ChecksumOps({"checksum": {"enabled_algorithms": ["md5", "bogus", "sha256"]}}, None, None)
        self.assertEqual(ops.get_available_algorithms(), ["md5", "sha256"])


if __name__ == "__main__":
    unittest.main()

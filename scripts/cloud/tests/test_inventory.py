import unittest
from unittest.mock import patch

from scripts.cloud.aws_readonly_inventory import COMMANDS, inventory


class Fake:
    returncode = 0
    stdout = '{"Account":"123456789012"}'


class InventoryTests(unittest.TestCase):
    def test_only_approved_read_methods(self):
        self.assertTrue(
            all(args[1].startswith(("get-", "list-", "describe-")) for args in COMMANDS.values())
        )
        self.assertTrue(
            {
                "network_interfaces",
                "vpc_links",
                "secrets",
                "rds_retained_backups",
                "snapshots",
                "backend_buckets",
            }.issubset(COMMANDS)
        )

    def test_fails_on_mismatched_account(self):
        with patch("scripts.cloud.aws_readonly_inventory.subprocess.run", return_value=Fake()):
            with self.assertRaises(RuntimeError):
                inventory(profile="safe", region="ap-south-1", expected_account="000000000000")

    def test_requires_account(self):
        with self.assertRaises(ValueError):
            inventory(profile="", region="ap-south-1", expected_account="123456789012")


if __name__ == "__main__":
    unittest.main()

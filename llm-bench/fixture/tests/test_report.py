import unittest

from inventory.models import Item
from inventory.report import low_stock_warning, stock_table, tag_summary
from inventory.store import Store


def sample() -> Store:
    return Store([
        Item("A1", "Anvil", 3, 120.0, ["Heavy", "metal"]),
        Item("B2", "Bolt", 400, 0.15, ["metal"]),
    ])


class ReportTest(unittest.TestCase):
    def test_table_has_header_and_rows(self):
        lines = stock_table(sample()).splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn("Anvil", lines[1])

    def test_low_stock_warning(self):
        self.assertEqual(low_stock_warning(sample()), "Low stock: Anvil (3)")

    def test_tag_summary(self):
        self.assertEqual(tag_summary(sample()), {"heavy": 1, "metal": 2})


if __name__ == "__main__":
    unittest.main()

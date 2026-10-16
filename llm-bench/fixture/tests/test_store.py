import unittest

from inventory.models import Item
from inventory.store import Store


def sample() -> Store:
    return Store([
        Item("A1", "Anvil", 3, 120.0, ["heavy", "metal"]),
        Item("B2", "Bolt", 400, 0.15, ["metal"]),
        Item("C3", "Cable", 12, 4.5, ["electrical"]),
    ])


class StoreTest(unittest.TestCase):
    def test_iteration_is_sorted_by_sku(self):
        self.assertEqual([i.sku for i in sample()], ["A1", "B2", "C3"])

    def test_duplicate_sku_rejected(self):
        store = sample()
        with self.assertRaises(KeyError):
            store.add(Item("A1", "Other", 1, 1.0))

    def test_sell_and_restock(self):
        store = sample()
        store.sell("C3", 2)
        store.restock("C3", 5)
        self.assertEqual(store.get("C3").quantity, 15)

    def test_cannot_oversell(self):
        with self.assertRaises(ValueError):
            sample().sell("A1", 4)

    def test_low_stock(self):
        self.assertEqual([i.sku for i in sample().low_stock()], ["A1"])

    def test_tagged_is_case_insensitive(self):
        self.assertEqual([i.sku for i in sample().tagged("METAL")], ["A1", "B2"])


if __name__ == "__main__":
    unittest.main()

from collections.abc import Iterable, Iterator

from inventory.models import Item


class Store:
    def __init__(self, items: Iterable[Item] = ()) -> None:
        self._items: dict[str, Item] = {}
        for item in items:
            self.add(item)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[Item]:
        return iter(sorted(self._items.values(), key=lambda i: i.sku))

    def __contains__(self, sku: str) -> bool:
        return sku in self._items

    def add(self, item: Item) -> None:
        if item.sku in self._items:
            raise KeyError(f"duplicate sku {item.sku}")
        self._items[item.sku] = item

    def get(self, sku: str) -> Item:
        try:
            return self._items[sku]
        except KeyError:
            raise KeyError(f"unknown sku {sku}") from None

    def remove(self, sku: str) -> Item:
        item = self.get(sku)
        del self._items[sku]
        return item

    def restock(self, sku: str, amount: int) -> Item:
        if amount <= 0:
            raise ValueError("amount must be positive")
        item = self.get(sku)
        item.quantity += amount
        return item

    def sell(self, sku: str, amount: int) -> Item:
        if amount <= 0:
            raise ValueError("amount must be positive")
        item = self.get(sku)
        if amount > item.quantity:
            raise ValueError(f"only {item.quantity} of {sku} in stock")
        item.quantity -= amount
        return item

    def low_stock(self, threshold: int = 5) -> list[Item]:
        return [item for item in self if item.is_low_stock(threshold)]

    def tagged(self, tag: str) -> list[Item]:
        return [item for item in self if item.has_tag(tag)]

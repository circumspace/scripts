from dataclasses import dataclass, field


@dataclass
class Item:
    sku: str
    name: str
    quantity: int
    unit_price: float
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.sku:
            raise ValueError("sku must not be empty")
        if self.quantity < 0:
            raise ValueError("quantity must not be negative")
        if self.unit_price < 0:
            raise ValueError("unit_price must not be negative")

    def is_low_stock(self, threshold: int = 5) -> bool:
        return self.quantity <= threshold

    def has_tag(self, tag: str) -> bool:
        return tag.lower() in (t.lower() for t in self.tags)

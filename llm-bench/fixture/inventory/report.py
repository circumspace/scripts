from inventory.store import Store


def stock_table(store: Store) -> str:
    lines = [f"{'SKU':<10} {'NAME':<24} {'QTY':>5} {'PRICE':>9}"]
    for item in store:
        lines.append(f"{item.sku:<10} {item.name:<24} {item.quantity:>5} {item.unit_price:>9.2f}")
    return "\n".join(lines)


def low_stock_warning(store: Store, threshold: int = 5) -> str:
    low = store.low_stock(threshold)
    if not low:
        return "All items sufficiently stocked."
    names = ", ".join(f"{item.name} ({item.quantity})" for item in low)
    return f"Low stock: {names}"


def tag_summary(store: Store) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in store:
        for tag in item.tags:
            key = tag.lower()
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))

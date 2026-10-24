import argparse
import json
import sys

from inventory.models import Item
from inventory.report import low_stock_warning, stock_table, tag_summary
from inventory.store import Store


def load_store(path: str) -> Store:
    with open(path) as f:
        raw = json.load(f)
    return Store(Item(**entry) for entry in raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="inventory")
    parser.add_argument("file", help="JSON file with a list of items")
    parser.add_argument("command", choices=["table", "low", "tags"])
    parser.add_argument("--threshold", type=int, default=5)
    args = parser.parse_args(argv)
    store = load_store(args.file)
    if args.command == "table":
        print(stock_table(store))
    elif args.command == "low":
        print(low_stock_warning(store, args.threshold))
    else:
        print(json.dumps(tag_summary(store), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

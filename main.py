import argparse
import logging
import sys

from migrate.runner import run

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")


def main():
    parser = argparse.ArgumentParser(
        description="MoySklad: bitta bazadagi spravochniklarni (uom, currency, "
        "productfolder, counterpartyfolder, store, counterparty, product, "
        "service, variant, bundle, custom field) API orqali boshqa bazaga ko'chiradi."
    )
    parser.add_argument(
        "--only",
        help="Faqat shu turlarni ko'chirish, vergul bilan ajratib: masalan product,service",
        default=None,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Hech narsa yozmaydi, faqat necha ta element ko'chirilishini ko'rsatadi",
    )
    args = parser.parse_args()
    only = set(args.only.split(",")) if args.only else None

    try:
        run(only=only, dry_run=args.dry_run)
    except RuntimeError as exc:
        logging.error(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()

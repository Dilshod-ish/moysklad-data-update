import argparse
import logging
import sys

from migrate.client import MoySkladClient
from migrate.config import load_config
from migrate.reschedule import TIME_SCHEDULE, run

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Yangi (DEST) bazadagi hujjatlarning sanasini saqlab, kunlik vaqtini "
            "hujjat turiga qarab belgilangan jadval bo'yicha to'g'irlaydi — shunda "
            "bir kundagi hujjatlar (masalan приемка ertalab, отгрузка kechqurun) "
            "to'g'ri xronologik tartibda bo'ladi."
        )
    )
    parser.add_argument(
        "--only",
        help="Faqat shu turlarni tuzatish, vergul bilan ajratib: masalan supply,demand",
        default=None,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Hech narsa yozmaydi, faqat nechta hujjat o'zgarishini ko'rsatadi",
    )
    args = parser.parse_args()
    only = set(args.only.split(",")) if args.only else None

    _, dest_creds = load_config()
    client = MoySkladClient(dest_creds)

    try:
        summary = run(client, only=only, dry_run=args.dry_run)
    except RuntimeError as exc:
        logging.error(str(exc))
        sys.exit(1)

    logging.info("Jadval: %s", TIME_SCHEDULE)
    failed = [k for k, v in summary.items() if v is None]
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()

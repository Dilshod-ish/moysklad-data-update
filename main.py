import argparse
import logging
import sys

from migrate.runner import run

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")


def main():
    parser = argparse.ArgumentParser(
        description="MoySklad: bitta bazadagi spravochniklar (uom, currency, "
        "productfolder, store, counterparty, product, "
        "service, variant, bundle, employee, organization, project, contract, "
        "custom fieldlar) va hujjatlarni (enter, loss, move, inventory, supply, "
        "demand, order, invoice, payment) API orqali boshqa bazaga ko'chiradi."
    )
    parser.add_argument(
        "--only",
        help="Faqat shu turlarni ko'chirish, vergul bilan ajratib: masalan product,service,demand",
        default=None,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Hech narsa yozmaydi, faqat necha ta element ko'chirilishini ko'rsatadi",
    )
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help=(
            "Ilgari ko'chirilgan (allaqachon mavjud) elementlarni ham qayta "
            "tekshiradi va manba bazadagidan farq qilsa, maqsad bazadagisini "
            "yangilaydi (masalan, kod yangilangandan keyin noto'g'ri "
            "yaratilgan hujjatlarni tuzatish uchun)."
        ),
    )
    args = parser.parse_args()
    only = set(args.only.split(",")) if args.only else None

    try:
        failed = run(only=only, dry_run=args.dry_run, update_existing=args.update_existing)
    except RuntimeError as exc:
        logging.error(str(exc))
        sys.exit(1)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()

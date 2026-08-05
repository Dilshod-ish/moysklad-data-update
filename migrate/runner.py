import logging
from typing import Optional

from .client import MoySkladClient
from .config import load_config
from .documents import DOCUMENT_TYPES, migrate_document_type
from .entities import ENTITY_TYPES, build_maps, migrate_entity_type
from .pricetypes import migrate_price_types

log = logging.getLogger("moysklad.runner")


def run(only: Optional[set] = None, dry_run: bool = False, update_existing: bool = False):
    source_creds, dest_creds = load_config()
    source_client = MoySkladClient(source_creds)
    dest_client = MoySkladClient(dest_creds)
    maps = build_maps()

    failed = []

    log.info("Narx turlari (pricetype) sinxronlanmoqda...")
    try:
        migrate_price_types(source_client, dest_client, maps, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001
        log.error("pricetype: sinxronlanmadi: %s", exc)
        failed.append("pricetype")

    for cfg in ENTITY_TYPES:
        if only and cfg["key"] not in only:
            continue
        try:
            migrate_entity_type(
                source_client, dest_client, cfg, maps, dry_run=dry_run, update_existing=update_existing
            )
        except Exception as exc:  # noqa: BLE001
            log.error("%s: turi ko'chirilmadi, keyingisiga o'tiladi: %s", cfg["key"], exc)
            failed.append(cfg["key"])

    for cfg in DOCUMENT_TYPES:
        if only and cfg["key"] not in only:
            continue
        try:
            migrate_document_type(
                source_client, dest_client, cfg, maps, dry_run=dry_run, update_existing=update_existing
            )
        except Exception as exc:  # noqa: BLE001
            log.error("%s: turi ko'chirilmadi, keyingisiga o'tiladi: %s", cfg["key"], exc)
            failed.append(cfg["key"])

    if failed:
        log.warning("Quyidagi turlar to'liq ko'chirilmadi: %s", ", ".join(failed))

    if dry_run:
        log.info("Dry-run yakunlandi — hech narsa yozilmadi.")
    else:
        log.info("Migratsiya yakunlandi.")

    return failed

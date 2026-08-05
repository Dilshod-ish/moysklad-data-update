import logging

log = logging.getLogger("moysklad.pricetypes")


def migrate_price_types(source_client, dest_client, maps: dict, dry_run: bool = False):
    """Narx turlarini (Тип цены) nomi bo'yicha moslashtiradi; maqsad bazada
    yo'q bo'lganlarini yaratadi. product/counterparty dagi salePrices shu
    orqali to'g'ri narx turiga bog'lanadi."""
    source_settings = source_client.get("context/companysettings")
    dest_settings = dest_client.get("context/companysettings")

    source_types = source_settings.get("priceTypes", [])
    dest_types = list(dest_settings.get("priceTypes", []))
    dest_by_name = {pt["name"]: pt for pt in dest_types}

    missing = [pt["name"] for pt in source_types if pt["name"] not in dest_by_name]
    log.info("Narx turlari: manbada %d ta, maqsadda yo'q bo'lgani %d ta", len(source_types), len(missing))

    if missing and not dry_run:
        for name in missing:
            dest_types.append({"name": name})
        updated_settings = dest_client.put("context/companysettings", {"priceTypes": dest_types})
        dest_types = updated_settings.get("priceTypes", dest_types)
        dest_by_name = {pt["name"]: pt for pt in dest_types}

    id_map = maps["entity"].setdefault("pricetype", {})
    for pt in source_types:
        dest_pt = dest_by_name.get(pt["name"])
        if dest_pt:
            id_map[pt["id"]] = {"meta": dest_pt["meta"]}

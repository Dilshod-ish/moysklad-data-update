import logging
import re

log = logging.getLogger("moysklad.pricetypes")

_RE_ID = re.compile(r"([0-9a-fA-F-]{36})(?:$|\?)")


def migrate_price_types(source_client, dest_client, maps: dict, dry_run: bool = False):
    """Narx turlarini (Тип цены) nomi bo'yicha moslashtiradi; maqsad bazada
    yo'q bo'lganlarini yaratadi. product/counterparty dagi salePrices shu
    orqali to'g'ri narx turiga bog'lanadi. Shu bilan birga maqsad bazaning
    hisob (учётная) valyutasi ID'sini ham maps'ga yozadi — hujjatlarda shu
    valyuta uchun kurs (rate) har doim 1 bo'lishi shart."""
    source_settings = source_client.get("context/companysettings")
    dest_settings = dest_client.get("context/companysettings")

    dest_currency_href = (dest_settings.get("currency") or {}).get("meta", {}).get("href", "")
    m = _RE_ID.search(dest_currency_href)
    if m:
        maps["base_currency_id"] = m.group(1)

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

import logging

from .attributes import migrate_attributes, resolve_attribute_values
from .mapper import resolve_refs

log = logging.getLogger("moysklad.entities")

# Ko'chirish tartibi muhim: har bir tur o'zidan oldingi turlarga bog'liq bo'lishi
# mumkin (masalan, product -> productfolder, uom). "self_referential" bo'lgan
# turlar (papkalar) o'z-o'ziga (ota-guruh) bog'lanishga ega, shuning uchun ular
# ikkinchi bosqichda (yaratilgandan keyin) tuzatiladi.
ENTITY_TYPES = [
    {"key": "uom", "path": "entity/uom", "self_referential": False, "has_attributes": False},
    {"key": "currency", "path": "entity/currency", "self_referential": False, "has_attributes": False},
    {"key": "productfolder", "path": "entity/productfolder", "self_referential": True, "has_attributes": False},
    {"key": "counterpartyfolder", "path": "entity/counterpartyfolder", "self_referential": True, "has_attributes": False},
    {"key": "store", "path": "entity/store", "self_referential": False, "has_attributes": True},
    {"key": "counterparty", "path": "entity/counterparty", "self_referential": False, "has_attributes": True},
    {"key": "product", "path": "entity/product", "self_referential": False, "has_attributes": True},
    {"key": "service", "path": "entity/service", "self_referential": False, "has_attributes": True},
    {"key": "variant", "path": "entity/variant", "self_referential": False, "has_attributes": False},
    {"key": "bundle", "path": "entity/bundle", "self_referential": False, "has_attributes": True},
]

# Bular hisoblanadigan (read-only) yoki akkauntga xos tizim maydonlari —
# yangi obyekt yaratishda yuborilmaydi/yuborilmasligi kerak.
TOP_LEVEL_STRIP = {
    "id",
    "accountId",
    "meta",
    "updated",
    "created",
    "shared",
    "syncId",
    "stock",
    "quantity",
    "reserve",
    "inTransit",
    "version",
}


def build_maps() -> dict:
    return {"entity": {}, "attribute": {}, "customentity": {}, "customentity_dict": {}}


def prepare_item(item: dict, entity_type: str, maps: dict) -> dict:
    cleaned = {k: v for k, v in item.items() if k not in TOP_LEVEL_STRIP}
    cleaned["externalCode"] = item["id"]

    attrs = cleaned.pop("attributes", None)
    resolved = resolve_refs(cleaned, maps)
    if attrs:
        new_attrs = resolve_attribute_values(attrs, entity_type, maps)
        if new_attrs:
            resolved["attributes"] = new_attrs

    return resolved


def migrate_entity_type(source_client, dest_client, cfg: dict, maps: dict, dry_run: bool = False):
    key = cfg["key"]
    path = cfg["path"]
    log.info("=== %s ===", key)

    source_items = source_client.get_all(path)
    log.info("%s: manbada %d ta element topildi", key, len(source_items))

    id_map = maps["entity"].setdefault(key, {})
    if not source_items:
        return

    dest_items = dest_client.get_all(path)
    dest_by_ext = {d.get("externalCode"): d for d in dest_items if d.get("externalCode")}

    if cfg.get("has_attributes") and not dry_run:
        migrate_attributes(source_client, dest_client, key, maps)

    already = 0
    for item in source_items:
        existing = dest_by_ext.get(item["id"])
        if existing:
            id_map[item["id"]] = {"meta": existing["meta"]}
            already += 1

    remaining = [item for item in source_items if item["id"] not in id_map]
    log.info("%s: %d ta allaqachon mavjud, %d ta yaratiladi", key, already, len(remaining))

    if dry_run or not remaining:
        return

    to_create = [(item["id"], prepare_item(item, key, maps)) for item in remaining]
    created = dest_client.bulk_create(path, [payload for _, payload in to_create])
    created_by_ext = {c.get("externalCode"): c for c in created if c.get("externalCode")}

    for source_id, _ in to_create:
        created_obj = created_by_ext.get(source_id)
        if created_obj:
            id_map[source_id] = {"meta": created_obj["meta"]}
        else:
            log.error("%s: %s uchun natija topilmadi (yaratilmagan bo'lishi mumkin)", key, source_id)

    if cfg.get("self_referential"):
        log.info("%s: ierarxik (ota-guruh) bog'lanishlar tuzatilmoqda", key)
        updates = []
        for item in source_items:
            dest_meta = id_map.get(item["id"])
            if not dest_meta:
                continue
            payload = prepare_item(item, key, maps)
            payload["meta"] = dest_meta["meta"]
            updates.append(payload)
        if updates:
            dest_client.bulk_update(path, updates)

import logging

from .attributes import migrate_attributes, resolve_attribute_values
from .mapper import payload_changed, resolve_refs

log = logging.getLogger("moysklad.entities")

# Ko'chirish tartibi muhim: har bir tur o'zidan oldingi turlarga bog'liq bo'lishi
# mumkin (masalan, product -> productfolder, uom; contract -> organization,
# counterparty). "self_referential" bo'lgan turlar (papkalar) o'z-o'ziga
# (ota-guruh) bog'lanishga ega, shuning uchun ular ikkinchi bosqichda
# (yaratilgandan keyin) tuzatiladi. "sub_resources" — obyektga tegishli, alohida
# sub-to'plam sifatida olinadigan ma'lumotlar (masalan, bank hisoblari).
#
# "match_by_name": True — MoySklad har bir yangi akkauntda ba'zi standart
# elementlarni (birlik "шт", "Основной склад", "Основной" bo'lim va h.k.)
# oldindan yaratib qo'yadi, ularning nomi manba bazadagi bilan bir xil
# bo'lishi mumkin. Bu turlar uchun nom bo'yicha ham moslashtiramiz, aks
# holda MoySklad "nom yagona bo'lishi kerak" xatosini beradi.
ENTITY_TYPES = [
    {"key": "uom", "path": "entity/uom", "match_by_name": True},
    {"key": "currency", "path": "entity/currency", "match_by_name": True},
    {"key": "group", "path": "entity/group", "match_by_name": True},
    {"key": "expenseitem", "path": "entity/expenseitem", "match_by_name": True},
    {"key": "employee", "path": "entity/employee", "match_by_name": True},
    {"key": "organization", "path": "entity/organization", "sub_resources": ["accounts"]},
    {"key": "productfolder", "path": "entity/productfolder", "self_referential": True},
    {"key": "store", "path": "entity/store", "match_by_name": True},
    {
        "key": "counterparty",
        "path": "entity/counterparty",
        "has_attributes": True,
        "sub_resources": ["accounts"],
    },
    {"key": "project", "path": "entity/project"},
    {"key": "contract", "path": "entity/contract", "has_attributes": True},
    {"key": "product", "path": "entity/product", "has_attributes": True},
    {"key": "service", "path": "entity/service", "has_attributes": True},
    {"key": "variant", "path": "entity/variant"},
    {"key": "bundle", "path": "entity/bundle", "has_attributes": True},
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

# Ba'zi turlar uchun qo'shimcha maydonlar ham olib tashlanadi.
_PRODUCT_LIKE_STRIP = {"code"}  # "code" (artikul) akkaunt bo'yicha yagona bo'lishi
# shart, lekin manba ma'lumotida ko'plab mahsulotlar bo'sh yoki takrorlangan
# "code"ga ega bo'lishi mumkin — shuning uchun uni ko'chirmaymiz.
EXTRA_STRIP = {
    # Yangi akkauntning hisob (учётная) valyutasi kursi har doim 1 bo'lishi
    # shart — manbadan kursni ko'chirsak, MoySklad buni rad etadi.
    "currency": {"rate"},
    "product": _PRODUCT_LIKE_STRIP,
    "service": _PRODUCT_LIKE_STRIP,
    "variant": _PRODUCT_LIKE_STRIP,
    "bundle": _PRODUCT_LIKE_STRIP,
}

SUB_RESOURCE_STRIP = {"id", "accountId", "meta", "updated", "created"}

# Ba'zi ichki (nested) ro'yxatlar o'zining "id"/"meta" o'ziga xos
# identifikatorlariga ega (masalan, tovar qadoqlari — "packs"), bular yangi
# obyekt yaratishda hech narsani anglatmaydi (server o'zi belgilaydi) va
# manba akkauntga xos bo'lgani uchun MoySklad "topilmadi" deb rad etadi.
# Shuning uchun faqat shu ikki maydonni olib tashlab, qolgan haqiqiy
# ma'lumotni (masalan "uom", "barcodes") saqlab qolamiz.
NESTED_STRIP = {
    "product": {"packs": {"id", "meta"}},
    "variant": {"packs": {"id", "meta"}},
    "bundle": {"packs": {"id", "meta"}},
}


def build_maps() -> dict:
    return {
        "entity": {},
        "attribute": {},
        "customentity": {},
        "customentity_dict": {},
        "state": {},
        "account": {},
    }


def prepare_item(item: dict, entity_type: str, maps: dict) -> dict:
    strip = TOP_LEVEL_STRIP | EXTRA_STRIP.get(entity_type, set())
    cleaned = {k: v for k, v in item.items() if k not in strip}
    cleaned["externalCode"] = item["id"]

    for field, sub_strip in NESTED_STRIP.get(entity_type, {}).items():
        rows = cleaned.get(field)
        if isinstance(rows, list):
            cleaned[field] = [
                {k: v for k, v in row.items() if k not in sub_strip}
                for row in rows
                if isinstance(row, dict)
            ]

    attrs = cleaned.pop("attributes", None)
    resolved = resolve_refs(cleaned, maps)
    if attrs:
        new_attrs = resolve_attribute_values(attrs, entity_type, maps)
        if new_attrs:
            resolved["attributes"] = new_attrs

    return resolved


def migrate_sub_resource(
    source_client,
    dest_client,
    parent_path: str,
    source_parent_id: str,
    dest_parent_id: str,
    sub_name: str,
    maps: dict,
):
    """Ota obyektga tegishli sub-to'plamni (masalan, bank hisoblari)
    manbadan maqsad obyektga ko'chiradi va (agar bank hisobi bo'lsa)
    to'lov hujjatlarida foydalanish uchun id_map'ga yozadi."""
    source_items = source_client.get_all(f"{parent_path}/{source_parent_id}/{sub_name}")
    if not source_items:
        return

    dest_items = dest_client.get_all(f"{parent_path}/{dest_parent_id}/{sub_name}")
    dest_by_ext = {d.get("externalCode"): d for d in dest_items if d.get("externalCode")}

    to_create = []
    for it in source_items:
        if it["id"] not in dest_by_ext:
            cleaned = {k: v for k, v in it.items() if k not in SUB_RESOURCE_STRIP}
            cleaned["externalCode"] = it["id"]
            # Bank hisobi kabi sub-resurslar ham valyuta kabi boshqa
            # obyektlarga havola qilishi mumkin — shularni ham bog'laymiz.
            cleaned = resolve_refs(cleaned, maps)
            to_create.append(cleaned)

    if to_create:
        created = dest_client.bulk_create(f"{parent_path}/{dest_parent_id}/{sub_name}", to_create)
        for c in created:
            if c.get("externalCode"):
                dest_by_ext[c["externalCode"]] = c

    if sub_name == "accounts":
        parent_type = parent_path.rsplit("/", 1)[-1]
        account_map = maps["account"].setdefault((parent_type, source_parent_id), {})
        for it in source_items:
            dest_item = dest_by_ext.get(it["id"])
            if dest_item:
                account_map[it["id"]] = {"meta": dest_item["meta"]}


def migrate_entity_type(
    source_client, dest_client, cfg: dict, maps: dict, dry_run: bool = False, update_existing: bool = False
):
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
    match_by_name = cfg.get("match_by_name", False)
    dest_by_name = {d["name"]: d for d in dest_items if d.get("name")} if match_by_name else {}

    if cfg.get("has_attributes") and not dry_run:
        migrate_attributes(source_client, dest_client, key, maps)

    # dest_by_source: shu turdagi barcha manba elementlariga mos maqsad
    # obyektlar (avvaldan mavjud + shu safar yaratilganlar birga) — bular
    # sub-resurslarni (masalan, bank hisoblarini) qayta ishga tushirishlarda
    # ham to'liq ko'chirish uchun kerak.
    dest_by_source: dict = {}
    # already_items: bu safar YANGI yaratilmagan, ilgari yaratilgan/mos
    # topilgan elementlar — faqat shular "yangilash" (update_existing)
    # bosqichida qayta tekshiriladi.
    already_items: list = []

    already = 0
    for item in source_items:
        existing = dest_by_ext.get(item["id"])
        if not existing and match_by_name:
            existing = dest_by_name.get(item.get("name"))
        if existing:
            id_map[item["id"]] = {"meta": existing["meta"]}
            dest_by_source[item["id"]] = existing
            already_items.append(item)
            already += 1

    remaining = [item for item in source_items if item["id"] not in id_map]
    log.info("%s: %d ta allaqachon mavjud, %d ta yaratiladi", key, already, len(remaining))

    if not dry_run and remaining:
        to_create = [(item["id"], prepare_item(item, key, maps)) for item in remaining]
        created = dest_client.bulk_create(path, [payload for _, payload in to_create])
        created_by_ext = {c.get("externalCode"): c for c in created if c.get("externalCode")}
        # Ba'zi turlar (masalan currency) yaratilgan obyektda externalCode'ni
        # aks ettirmasligi mumkin — nom bo'yicha ham urinib ko'ramiz.
        created_by_name = {c["name"]: c for c in created if c.get("name")} if match_by_name else {}

        for source_id, payload in to_create:
            created_obj = created_by_ext.get(source_id)
            if not created_obj and match_by_name:
                created_obj = created_by_name.get(payload.get("name"))
            if created_obj:
                id_map[source_id] = {"meta": created_obj["meta"]}
                dest_by_source[source_id] = created_obj
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

    if not dry_run and update_existing and already_items:
        log.info("%s: %d ta mavjud element o'zgarishlarga tekshirilmoqda", key, len(already_items))
        updates = []
        for item in already_items:
            existing = dest_by_source.get(item["id"])
            if not existing:
                continue
            payload = prepare_item(item, key, maps)
            if payload_changed(payload, existing):
                payload["meta"] = existing["meta"]
                updates.append(payload)
        if updates:
            dest_client.bulk_update(path, updates)
            log.info("%s: %d ta mavjud element yangilandi", key, len(updates))

    if not dry_run:
        for sub_name in cfg.get("sub_resources", []):
            log.info("%s: sub-resurs '%s' ko'chirilmoqda", key, sub_name)
            for source_id, dest_obj in dest_by_source.items():
                migrate_sub_resource(
                    source_client, dest_client, path, source_id, dest_obj["id"], sub_name, maps
                )

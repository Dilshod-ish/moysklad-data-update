import logging

from .attributes import migrate_attributes, resolve_attribute_values
from .mapper import parse_meta_href, payload_changed, resolve_refs

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
    {"key": "employee", "path": "entity/employee", "match_by_name": True, "include_archived": True},
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
    # "service" va "bundle" uchun MoySklad custom field (dopolnitelnoe pole)
    # metadata endpointini qo'llab-quvvatlamaydi ("Неопознанный путь", 1002) —
    # shuning uchun bu ikkisi uchun has_attributes o'rnatilmagan.
    {"key": "service", "path": "entity/service"},
    {"key": "variant", "path": "entity/variant"},
    {"key": "bundle", "path": "entity/bundle"},
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
    # "system" — valyuta MoySklad tomonidan "tizim" (standart, masalan RUB)
    # valyutasi deb belgilanganini bildiradi; bu o'qish-uchun-mo'ljallangan
    # (read-only) maydon — uni PUT/POST orqali o'zgartirishga urinish
    # "поле 'system' не может быть изменено" (3001) xatosini beradi.
    "currency": {"system"},
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
        "entity_by_name": {},
        "attribute": {},
        "attribute_dict": {},
        "customentity": {},
        "customentity_dict": {},
        "customentity_by_name": {},
        "state": {},
        "account": {},
    }


def prepare_item(item: dict, entity_type: str, maps: dict, dest_client=None) -> dict:
    strip = TOP_LEVEL_STRIP | EXTRA_STRIP.get(entity_type, set())
    cleaned = {k: v for k, v in item.items() if k not in strip}
    cleaned["externalCode"] = item["id"]

    # Manba bazaning O'ZINING hisob (учётная) valyutasi uchun kurs har doim 1
    # bo'lishi shart — maqsad bazada bu valyuta ham hisob valyutasi bo'lib
    # qoladi, shuning uchun "rate"ni olib tashlaymiz (MoySklad boshqacha
    # qiymatni rad etadi). Boshqa (chet el) valyutalarning kursi esa
    # saqlanadi — hisobot skriptlari "rate.currency.rate"ga tayanishi mumkin.
    if entity_type == "currency" and item["id"] == maps.get("source_base_currency_id"):
        cleaned.pop("rate", None)

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
        new_attrs = resolve_attribute_values(attrs, entity_type, maps, dest_client=dest_client)
        if new_attrs:
            resolved["attributes"] = new_attrs

    # MoySklad har bir salePrices yozuvida "priceType" bo'lishini talab
    # qiladi. Agar manbadagi narx turi kompaniya sozlamalaridan o'chirilgan
    # bo'lsa (orphaned/eskirgan), resolve_refs uni hal qila olmay, butun
    # "priceType" kalitini tashlab yuboradi — natijada MoySklad "поле
    # 'priceType' не может быть пустым" xatosini berib, BUTUN mahsulotni
    # rad etadi. Shuning uchun bunday chala qolgan narx yozuvlarini
    # (mahsulotning o'zi emas) chetlab o'tamiz.
    sale_prices = resolved.get("salePrices")
    if isinstance(sale_prices, list):
        valid_prices = [sp for sp in sale_prices if isinstance(sp, dict) and "priceType" in sp]
        dropped = len(sale_prices) - len(valid_prices)
        if dropped:
            log.warning(
                "%s (%s): %d ta narx (salePrices) o'tkazib yuborildi — narx turi "
                "manbada o'chirilgan/topilmadi",
                entity_type,
                item.get("name", item.get("id")),
                dropped,
            )
        resolved["salePrices"] = valid_prices

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

    if sub_name == "accounts":
        # MoySklad talabi: agar tashkilotda birorta ham hisob yo'q bo'lsa,
        # chet el valyutasidagi hisobni to'g'ridan-to'g'ri yaratib
        # bo'lmaydi — avval hisob (учётная) valyutasidagi hisob mavjud
        # bo'lishi kerak. Shuning uchun hisob valyutasidagisini birinchi
        # navbatda yaratamiz.
        def _is_base_currency(account: dict) -> bool:
            href = ((account.get("currency") or {}).get("meta") or {}).get("href", "")
            parsed = parse_meta_href(href)
            return bool(parsed and parsed[0] == "entity" and parsed[2] == maps.get("base_currency_id"))

        to_create.sort(key=lambda a: not _is_base_currency(a))

        # Agar hisob (учётная) valyutadagi hisob DEST'da hali umuman yo'q
        # (na avvaldan mavjud, na shu safar yaratilayotganlar orasida) —
        # MoySklad chet el valyutasidagi hisoblarni ham rad etadi ("хотя бы
        # один из расчетных счетов должен быть в валюте учета"). Bunday
        # holatda manba tashkilotning o'zida hisob valyutasidagi hisob
        # umuman yo'q demakdir — API darajasida chetlab o'tib bo'lmaydi,
        # shuning uchun urinib, N ta bir xil xatoni chiqarish o'rniga bitta
        # aniq tushuntirish bilan o'tkazib yuboramiz.
        has_base_anywhere = any(_is_base_currency(a) for a in to_create) or any(
            _is_base_currency(d) for d in dest_items
        )
        if to_create and maps.get("base_currency_id") and not has_base_anywhere:
            log.warning(
                "%s (id=%s): hisob (учётная) valyutadagi bank hisobi manbada yo'q, "
                "shuning uchun uning %d ta chet el valyutasidagi hisobi ko'chirilmadi "
                "(MoySklad kamida bitta hisob valyutasidagi hisobni talab qiladi). "
                "Tuzatish uchun MoySklad'da qo'lda shu tashkilot uchun hisob "
                "valyutasida bitta hisob yarating, so'ng skriptni qayta ishga tushiring.",
                parent_path.rsplit("/", 1)[-1],
                dest_parent_id,
                len(to_create),
            )
            to_create = []

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
    if cfg.get("include_archived"):
        # Ba'zi elementlar (masalan arxivlangan/ishdan bo'shatilgan
        # xodimlar) standart ro'yxatda ko'rinmasligi mumkin, lekin eski
        # hujjatlarning custom fieldlari hali ham ularga ishora qilishi
        # mumkin — shuning uchun arxivlanganlarni ham qo'shib olamiz.
        archived = source_client.get_all(path, params={"filter": "archived=true"})
        seen_ids = {it["id"] for it in source_items}
        source_items.extend(it for it in archived if it["id"] not in seen_ids)
    log.info("%s: manbada %d ta element topildi", key, len(source_items))

    id_map = maps["entity"].setdefault(key, {})
    if not source_items:
        return

    dest_items = dest_client.get_all(path)
    dest_by_ext = {d.get("externalCode"): d for d in dest_items if d.get("externalCode")}
    match_by_name = cfg.get("match_by_name", False)
    dest_by_name = {d["name"]: d for d in dest_items if d.get("name")} if match_by_name else {}

    if cfg.get("has_attributes") and not dry_run:
        try:
            migrate_attributes(source_client, dest_client, key, maps)
        except RuntimeError as exc:
            # Custom field (attribute) sinxronizatsiyasidagi xato butun
            # turning haqiqiy ma'lumotlarini (o'zini) ko'chirishga
            # to'sqinlik qilmasligi kerak — masalan ba'zi turlar
            # (service, bundle) custom fieldlarni umuman qo'llab-
            # quvvatlamaydi ("Неопознанный путь").
            log.error(
                "%s: custom fieldlar sinxronlanmadi (%s) — elementlarning o'zi baribir ko'chiriladi",
                key,
                exc,
            )

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
        to_create = [(item["id"], prepare_item(item, key, maps, dest_client=dest_client)) for item in remaining]
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
                dest_obj = dest_by_source.get(item["id"])
                if not dest_obj:
                    continue
                payload = prepare_item(item, key, maps, dest_client=dest_client)
                payload["meta"] = dest_obj["meta"]
                payload["id"] = dest_obj["id"]
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
            payload = prepare_item(item, key, maps, dest_client=dest_client)
            if payload_changed(payload, existing):
                payload["meta"] = existing["meta"]
                payload["id"] = existing["id"]
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

import logging
import re

log = logging.getLogger("moysklad.attributes")

# Bu turdagi custom fieldlar migratsiya qilinmaydi: "file" qiymati binar fayl
# bo'lib, qayta yuklashni talab qiladi (v1 doirasidan tashqarida).
SKIP_ATTRIBUTE_TYPES = {"file"}

_RE_CUSTOMENTITY_DICT = re.compile(r"/entity/customentity/([0-9a-fA-F-]{36})")
_RE_ATTR_META = re.compile(r"/entity/[a-zA-Z]+/metadata/attributes/([0-9a-fA-F-]{36})")
_RE_CUSTOMENTITY_VALUE = re.compile(r"/entity/customentity/([0-9a-fA-F-]{36})/([0-9a-fA-F-]{36})")


def get_attributes(client, entity_type: str) -> list:
    data = client.get(f"entity/{entity_type}/metadata/attributes")
    if isinstance(data, list):
        return data
    return data.get("rows", [])


def migrate_customentity_dict(source_client, dest_client, dict_id: str, dict_name: str, maps: dict):
    """Manbadagi custom entity (foydalanuvchi lug'ati)ni maqsad bazada topadi
    yoki yaratadi, elementlarini nom bo'yicha moslashtiradi/yaratadi."""
    if dict_id in maps["customentity_dict"]:
        return maps["customentity_dict"][dict_id], maps["customentity"].setdefault(dict_id, {})

    dest_dict = get_or_create_customentity_dict_by_name(dest_client, dict_name, maps, cache_key=dict_id)

    ce_map = maps["customentity"].setdefault(dict_id, {})
    source_elements = source_client.get_all(f"entity/customentity/{dict_id}")
    dest_elements = dest_client.get_all(f"entity/customentity/{dest_dict['id']}")
    dest_by_name = {e["name"]: e for e in dest_elements}

    to_create = [
        {"name": el["name"], "externalCode": el["id"]}
        for el in source_elements
        if el["name"] not in dest_by_name
    ]
    if to_create:
        created = dest_client.bulk_create(f"entity/customentity/{dest_dict['id']}", to_create)
        for c in created:
            dest_by_name[c["name"]] = c

    for el in source_elements:
        dest_el = dest_by_name.get(el["name"])
        if dest_el:
            ce_map[el["id"]] = {"meta": dest_el["meta"]}
        else:
            log.error("customentity elementi ko'chirilmadi: %s / %s", dict_name, el["name"])

    # Nomlar keshini ham to'ldiramiz — endi qiymatlarni nom bo'yicha
    # tiklash kerak bo'lsa (masalan buzilgan havolalar uchun), qayta
    # so'rov yubormasdan shu yerdan foydalanish mumkin.
    maps["customentity_by_name"][dest_dict["id"]] = dest_by_name

    return dest_dict, ce_map


def get_or_create_customentity_dict_by_name(dest_client, dict_name: str, maps: dict, cache_key=None):
    """Nomi bo'yicha customentity lug'atini shu ishga tushirish (run)
    doirasida keshlab, kerak bo'lsa yaratadi.

    Avval to'g'ridan-to'g'ri yaratishga (POST) urinamiz — chunki barcha
    lug'atlarni ro'yxat qiladigan "GET /entity/customentity" (bare)
    so'rovi haqiqiy hisobda "Не указан идентификатор объекта" (1012)
    xatosini berishi aniqlangan, shuning uchun ehtiyotkorlik uchun uni
    oldindan CHAQIRMAYMIZ. Lekin agar DEST'da shu nomdagi lug'at
    ALLAQACHON mavjud bo'lsa (masalan boshqa, buzilmagan havolali
    entity type orqali oldinroq yaratilgan bo'lsa), MoySklad "nom yagona
    bo'lishi kerak" (3006) xatosini beradi — aynan shu holatda, endi
    haqiqatan ham kerak bo'lgani uchun, ro'yxat so'rovini urinib ko'ramiz
    (agar u ham ishlamasa, aniq xato bilan to'xtaymiz).

    Ishga tushirishlar orasidagi (masalan --update-existing bilan qayta
    ishga tushirishdagi) idempotentlik esa custom fieldning o'zi
    (attribute) DEST'da allaqachon mavjud bo'lsa, uning o'z (endi to'g'ri)
    customEntityMeta'si orqali ta'minlanadi — qarang: _register_attribute_dict."""
    key = cache_key if cache_key is not None else f"name:{dict_name}"
    if key in maps["customentity_dict"]:
        return maps["customentity_dict"][key]

    try:
        dest_dict = dest_client.post("entity/customentity", {"name": dict_name})
        log.info("Yangi customentity lug'at yaratildi: %s", dict_name)
    except RuntimeError as exc:
        if "3006" not in str(exc) and "уникальности" not in str(exc):
            raise
        dest_dict = _find_customentity_dict_by_name(dest_client, dict_name)
        if not dest_dict:
            raise
        log.info("DEST'da allaqachon mavjud customentity lug'at topildi: %s", dict_name)

    maps["customentity_dict"][key] = dest_dict
    return dest_dict


def _find_customentity_dict_by_name(dest_client, dict_name: str):
    """"entity/customentity" ro'yxatini bir necha xil usulda (limit/offset
    bilan, ularsiz, nom bo'yicha filter bilan, metadata orqali) so'rab,
    nomi bo'yicha lug'atni qidiradi. Faqat
    get_or_create_customentity_dict_by_name lug'at ALLAQACHON DEST'da
    mavjudligini (nom to'qnashuvi xatosi orqali) aniqlagandan keyingina
    chaqiriladi."""
    attempts = (
        lambda: dest_client.get_all("entity/customentity"),
        lambda: _as_list(dest_client.get("entity/customentity")),
        lambda: _as_list(dest_client.get("entity/customentity", params={"filter": f"name={dict_name}"})),
        lambda: _as_list(dest_client.get("entity/customentity/metadata")),
    )
    last_exc = None
    for attempt in attempts:
        try:
            dest_dicts = attempt()
        except RuntimeError as exc:
            last_exc = exc
            continue
        found = next((d for d in dest_dicts if d.get("name") == dict_name), None)
        if found:
            return found
    log.error(
        "customentity lug'atlari ro'yxati olinmadi (%s) — '%s' nomli lug'at DEST'da "
        "allaqachon mavjud (nom to'qnashuvi xatosi), lekin uni API orqali topib "
        "bo'lmadi. TUZATISH: MoySklad'da DEST bazaga kiring -> Sozlamalar -> "
        "Пользовательские справочники -> '%s' nomli (bo'sh/ishlatilmagan) "
        "lug'atni toping va o'chiring, so'ng skriptni qayta ishga tushiring — "
        "shunda u avtomatik, to'g'ri elementlari bilan qayta yaratiladi.",
        last_exc,
        dict_name,
        dict_name,
    )
    return None


def _as_list(data) -> list:
    if isinstance(data, list):
        return data
    return data.get("rows", []) if isinstance(data, dict) else []


def get_or_create_customentity_element_by_name(dest_client, dest_dict: dict, element_name: str, maps: dict):
    """dest_dict ichida nomi bo'yicha elementni topadi yoki yaratadi.
    Manba elementining ID'si noma'lum bo'lgan (havolasi buzilgan)
    hollarda — faqat ko'rinadigan nomi asosida — ishlatiladi."""
    cache = maps["customentity_by_name"].get(dest_dict["id"])
    if cache is None:
        elements = dest_client.get_all(f"entity/customentity/{dest_dict['id']}")
        cache = {e["name"]: e for e in elements}
        maps["customentity_by_name"][dest_dict["id"]] = cache

    existing = cache.get(element_name)
    if existing:
        return existing

    created = dest_client.post(f"entity/customentity/{dest_dict['id']}", {"name": element_name})
    cache[element_name] = created
    return created


def migrate_attributes(source_client, dest_client, entity_type: str, maps: dict):
    """entity_type uchun custom field (dopolnitelnoe pole) ta'riflarini
    manbadan maqsad bazaga ko'chiradi, id_map["attribute"][entity_type] ni to'ldiradi."""
    source_attrs = get_attributes(source_client, entity_type)
    if not source_attrs:
        return
    dest_attrs = get_attributes(dest_client, entity_type)
    dest_by_name = {a["name"]: a for a in dest_attrs}
    attr_map = maps["attribute"].setdefault(entity_type, {})
    path = f"entity/{entity_type}/metadata/attributes"

    for attr in source_attrs:
        attr_type = attr.get("type")
        if attr_type in SKIP_ATTRIBUTE_TYPES:
            log.warning("Custom field o'tkazib yuborildi (turi qo'llab-quvvatlanmaydi): %s (%s)", attr["name"], attr_type)
            continue

        existing = dest_by_name.get(attr["name"])
        if existing:
            attr_map[attr["id"]] = existing
            if attr_type == "customentity":
                try:
                    _register_attribute_dict(source_client, dest_client, attr, maps, dest_attr=existing)
                except RuntimeError as exc:
                    # Bitta buzilgan/hal qilib bo'lmaydigan customentity lug'ati
                    # butun hujjat turini (yuzlab hujjatni) migratsiyadan
                    # chetlatmasligi kerak — shu fieldni o'tkazib yuboramiz,
                    # hujjatning o'zi va boshqa fieldlari baribir ko'chiriladi.
                    log.error(
                        "Custom field lug'ati aniqlanmadi: %s: %s — bu field qiymatlari "
                        "ko'chirilmaydi, lekin hujjatning o'zi ko'chiriladi",
                        attr["name"],
                        exc,
                    )
            continue

        payload = {
            "name": attr["name"],
            "type": attr_type,
            "required": attr.get("required", False),
        }
        if "showOnUi" in attr:
            payload["showOnUi"] = attr["showOnUi"]

        if attr_type == "customentity":
            try:
                dest_dict = _register_attribute_dict(source_client, dest_client, attr, maps)
            except RuntimeError as exc:
                log.error(
                    "Custom field lug'ati aniqlanmadi: %s: %s — bu field o'tkazib yuborildi, "
                    "hujjatning o'zi baribir ko'chiriladi",
                    attr["name"],
                    exc,
                )
                continue
            payload["customEntityMeta"] = dest_dict["meta"]

        try:
            created_attr = dest_client.post(path, payload)
        except RuntimeError as exc:
            log.error("Custom field yaratilmadi: %s (%s): %s", attr["name"], attr_type, exc)
            continue
        dest_by_name[attr["name"]] = created_attr
        attr_map[attr["id"]] = created_attr


def _register_attribute_dict(source_client, dest_client, attr: dict, maps: dict, dest_attr: dict = None):
    """customentity turidagi custom field uchun maqsad lug'atni aniqlaydi
    va maps["attribute_dict"][attr_id] ga yozadi — bu keyinroq, agar
    biror hujjatning qiymat havolasi buzilgan bo'lsa, nom bo'yicha
    tiklash uchun ishlatiladi.

    dest_attr — agar shu custom field DEST bazada allaqachon mavjud bo'lsa
    (masalan qayta ishga tushirishda), uning o'z customEntityMeta'si
    beriladi. Bu har doim to'g'ri (DEST'ning o'zida yaratilgan), manba
    (source) havolasining buzilgan-buzilmaganidan qat'i nazar — shunday
    qilib bir xil lug'at qayta-qayta yaratilmaydi."""
    dest_href = ((dest_attr or {}).get("customEntityMeta") or {}).get("href", "")
    dm = _RE_CUSTOMENTITY_DICT.search(dest_href)
    if dm:
        dest_dict = {"id": dm.group(1), "meta": dest_attr["customEntityMeta"]}
        maps["attribute_dict"][attr["id"]] = dest_dict
        return dest_dict

    dict_href = (attr.get("customEntityMeta") or {}).get("href", "")
    m = _RE_CUSTOMENTITY_DICT.search(dict_href)
    if m:
        dest_dict, _ce_map = migrate_customentity_dict(source_client, dest_client, m.group(1), attr["name"], maps)
    else:
        # Manba lug'ati havolasi buzilgan (masalan lug'at o'chirilgan) —
        # baribir hujjat qiymatlarida ko'rinadigan nom mavjud bo'ladi,
        # shuning uchun nom bo'yicha lug'at yaratamiz/topamiz.
        log.warning(
            "customentity lug'ati havolasi buzilgan: %s — qiymatlar nom bo'yicha tiklanadi",
            attr["name"],
        )
        dest_dict = get_or_create_customentity_dict_by_name(dest_client, attr["name"], maps)
    maps["attribute_dict"][attr["id"]] = dest_dict
    return dest_dict


def resolve_attribute_values(attrs: list, entity_type: str, maps: dict, dest_client=None) -> list:
    attr_map = maps["attribute"].get(entity_type, {})
    result = []
    for attr in attrs or []:
        href = (attr.get("meta") or {}).get("href", "")
        m = _RE_ATTR_META.search(href)
        if not m:
            continue
        attr_id = m.group(1)
        new_attr = attr_map.get(attr_id)
        if not new_attr:
            continue

        value = attr.get("value")
        if isinstance(value, dict) and "meta" in value:
            vhref = (value.get("meta") or {}).get("href", "")
            dm = _RE_CUSTOMENTITY_VALUE.search(vhref)
            new_val = maps["customentity"].get(dm.group(1), {}).get(dm.group(2)) if dm else None

            if new_val:
                value = {"meta": new_val["meta"], "name": value.get("name")}
            else:
                # Qiymatning havolasi buzilgan yoki topilmadi — lekin ko'rinadigan
                # nomi (value.name) hali ham mavjud bo'lishi mumkin. Shu nom
                # bo'yicha maqsad lug'atdan mos elementni topamiz/yaratamiz.
                elem_name = value.get("name")
                dest_dict = maps["attribute_dict"].get(attr_id)
                if not elem_name or not dest_dict or not dest_client:
                    continue
                dest_elem = get_or_create_customentity_element_by_name(dest_client, dest_dict, elem_name, maps)
                value = {"meta": dest_elem["meta"], "name": elem_name}

        result.append({"meta": new_attr["meta"], "value": value})
    return result

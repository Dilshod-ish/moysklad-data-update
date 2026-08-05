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

    dest_dicts = dest_client.get_all("entity/customentity")
    dest_dict = next((d for d in dest_dicts if d["name"] == dict_name), None)
    if not dest_dict:
        dest_dict = dest_client.post("entity/customentity", {"name": dict_name})
        log.info("Yangi customentity lug'at yaratildi: %s", dict_name)
    maps["customentity_dict"][dict_id] = dest_dict

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

    return dest_dict, ce_map


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
            continue

        payload = {
            "name": attr["name"],
            "type": attr_type,
            "required": attr.get("required", False),
        }
        if "showOnUi" in attr:
            payload["showOnUi"] = attr["showOnUi"]

        if attr_type == "customentity":
            dict_href = (attr.get("customEntityMeta") or {}).get("href", "")
            m = _RE_CUSTOMENTITY_DICT.search(dict_href)
            if not m:
                log.error("customentity lug'ati topilmadi: %s", attr["name"])
                continue
            dest_dict, _ce_map = migrate_customentity_dict(
                source_client, dest_client, m.group(1), attr["name"], maps
            )
            payload["customEntityMeta"] = dest_dict["meta"]

        try:
            created_attr = dest_client.post(path, payload)
        except RuntimeError as exc:
            log.error("Custom field yaratilmadi: %s (%s): %s", attr["name"], attr_type, exc)
            continue
        dest_by_name[attr["name"]] = created_attr
        attr_map[attr["id"]] = created_attr


def resolve_attribute_values(attrs: list, entity_type: str, maps: dict) -> list:
    attr_map = maps["attribute"].get(entity_type, {})
    result = []
    for attr in attrs or []:
        href = (attr.get("meta") or {}).get("href", "")
        m = _RE_ATTR_META.search(href)
        if not m:
            continue
        new_attr = attr_map.get(m.group(1))
        if not new_attr:
            continue

        value = attr.get("value")
        if isinstance(value, dict) and "meta" in value:
            vhref = (value.get("meta") or {}).get("href", "")
            dm = _RE_CUSTOMENTITY_VALUE.search(vhref)
            if not dm:
                continue
            new_val = maps["customentity"].get(dm.group(1), {}).get(dm.group(2))
            if not new_val:
                continue
            value = {"meta": new_val["meta"], "name": value.get("name")}

        result.append({"meta": new_attr["meta"], "value": value})
    return result

import re

DROP = object()

_RE_CUSTOMENTITY = re.compile(r"/entity/customentity/([0-9a-fA-F-]{36})/([0-9a-fA-F-]{36})(?:$|\?)")
_RE_ATTRIBUTE = re.compile(r"/entity/([a-zA-Z]+)/metadata/attributes/([0-9a-fA-F-]{36})(?:$|\?)")
_RE_STATE = re.compile(r"/entity/([a-zA-Z]+)/metadata/states/([0-9a-fA-F-]{36})(?:$|\?)")
_RE_ACCOUNT = re.compile(
    r"/entity/(organization|counterparty)/([0-9a-fA-F-]{36})/accounts/([0-9a-fA-F-]{36})(?:$|\?)"
)
_RE_STANDARD = re.compile(r"/(?:entity|context/companysettings)/([a-zA-Z]+)/([0-9a-fA-F-]{36})(?:$|\?)")


def parse_meta_href(href: str):
    """href'ni ('customentity', dict_id, element_id) / ('attribute', entity_type, attr_id) /
    ('state', doc_type, state_id) / ('account', parent_type, parent_id, account_id) /
    ('entity', type, id) ko'rinishiga aylantiradi. Tanib bo'lmasa None qaytaradi."""
    if not href:
        return None
    m = _RE_CUSTOMENTITY.search(href)
    if m:
        return ("customentity", m.group(1), m.group(2))
    m = _RE_ATTRIBUTE.search(href)
    if m:
        return ("attribute", m.group(1), m.group(2))
    m = _RE_STATE.search(href)
    if m:
        return ("state", m.group(1), m.group(2))
    m = _RE_ACCOUNT.search(href)
    if m:
        return ("account", m.group(1), m.group(2), m.group(3))
    m = _RE_STANDARD.search(href)
    if m:
        return ("entity", m.group(1), m.group(2))
    return None


# Bular — havola qilingan obyektning o'zidagi qulaylik uchun ko'rsatiladigan
# "ko'zgu" maydonlar (masalan priceType.name, uom.id). Bunday maydonlardan
# boshqasi yo'q bo'lsa, dict butunlay HAVOLA deb hisoblanadi va yangi
# meta bilan almashtiriladi. Lekin "operations" ichidagi kabi haqiqiy
# ma'lumot (masalan "sum") bo'lsa — dict ENDI havola emas, balki o'z
# ma'lumoti bilan havolani BIRGA saqlagan yozuv, shuning uchun faqat
# "meta"ning o'zi almashtiriladi, qolgan maydonlar saqlab qolinadi.
_MIRROR_KEYS = {"name", "id", "externalCode", "uuid", "code"}


def _resolve_meta(inner_meta: dict, maps: dict):
    """href'ga mos yangi meta'ni qaytaradi, topilmasa None."""
    href = inner_meta.get("href", "")
    parsed = parse_meta_href(href)
    if not parsed:
        return None
    kind = parsed[0]
    if kind == "entity":
        _, type_, old_id = parsed
        new_meta = maps["entity"].get(type_, {}).get(old_id)
    elif kind == "customentity":
        _, dict_id, elem_id = parsed
        new_meta = maps["customentity"].get(dict_id, {}).get(elem_id)
    elif kind == "state":
        _, doc_type, old_id = parsed
        new_meta = maps.get("state", {}).get(doc_type, {}).get(old_id)
    elif kind == "account":
        _, parent_type, parent_id, account_id = parsed
        new_meta = maps.get("account", {}).get((parent_type, parent_id), {}).get(account_id)
    else:
        new_meta = None
    return new_meta["meta"] if new_meta else None


def resolve_refs(node, maps: dict):
    """Ichki obyektdagi barcha {"meta": {...}} havolalarni maqsad bazadagi mos
    obyektlarga almashtiradi. Mos topilmasa (masalan, biz ko'chirmaydigan tur:
    fayl/rasm va h.k.) shu maydonni butunlay tashlab yuboradi, chunki
    manba akkauntdagi ID lar maqsad akkauntda hech narsani anglatmaydi."""
    if isinstance(node, dict):
        inner_meta = node.get("meta")
        if isinstance(inner_meta, dict) and "href" in inner_meta:
            other_keys = set(node.keys()) - {"meta"}

            if other_keys <= _MIRROR_KEYS:
                # Toza havola (masalan salePrices ichidagi priceType, uom) —
                # butun dict yangi meta bilan almashtiriladi.
                new_meta = _resolve_meta(inner_meta, maps)
                return {"meta": new_meta} if new_meta else DROP

            # Aralash yozuv (masalan to'lov hujjatidagi "operations" elementi:
            # {"meta": ..., "sum": N}) — faqat "meta" almashtiriladi, qolgan
            # haqiqiy ma'lumot (sum va h.k.) saqlanib qoladi. Havola hal
            # qilinmasa, butun yozuv ma'nosiz bo'lib qoladi — shuning uchun
            # butunlay tashlanadi.
            new_meta = _resolve_meta(inner_meta, maps)
            if not new_meta:
                return DROP
            out = {"meta": new_meta}
            for key, value in node.items():
                if key == "meta" or key in _MIRROR_KEYS:
                    continue
                resolved = resolve_refs(value, maps)
                if resolved is not DROP:
                    out[key] = resolved
            return out

        out = {}
        for key, value in node.items():
            resolved = resolve_refs(value, maps)
            if resolved is DROP:
                continue
            out[key] = resolved
        return out

    if isinstance(node, list):
        result = []
        for value in node:
            resolved = resolve_refs(value, maps)
            if resolved is not DROP:
                result.append(resolved)
        return result

    return node


def payload_changed(payload: dict, existing: dict) -> bool:
    """Hisoblangan payload maqsad bazadagi mavjud obyektdan farq qiladimi
    tekshiradi — faqat biz yozadigan maydonlar bo'yicha (dest'ning o'zi
    qo'shgan qo'shimcha maydonlarga e'tibor berilmaydi)."""
    for key, value in payload.items():
        if key == "externalCode":
            continue
        if existing.get(key) != value:
            return True
    return False

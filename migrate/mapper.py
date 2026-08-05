import re

DROP = object()

_RE_CUSTOMENTITY = re.compile(r"/entity/customentity/([0-9a-fA-F-]{36})/([0-9a-fA-F-]{36})(?:$|\?)")
_RE_ATTRIBUTE = re.compile(r"/entity/([a-zA-Z]+)/metadata/attributes/([0-9a-fA-F-]{36})(?:$|\?)")
_RE_STANDARD = re.compile(r"/(?:entity|context/companysettings)/([a-zA-Z]+)/([0-9a-fA-F-]{36})(?:$|\?)")


def parse_meta_href(href: str):
    """href'ni ('customentity', dict_id, element_id) / ('attribute', entity_type, attr_id) /
    ('entity', type, id) ko'rinishiga aylantiradi. Tanib bo'lmasa None qaytaradi."""
    if not href:
        return None
    m = _RE_CUSTOMENTITY.search(href)
    if m:
        return ("customentity", m.group(1), m.group(2))
    m = _RE_ATTRIBUTE.search(href)
    if m:
        return ("attribute", m.group(1), m.group(2))
    m = _RE_STANDARD.search(href)
    if m:
        return ("entity", m.group(1), m.group(2))
    return None


def resolve_refs(node, maps: dict):
    """Ichki obyektdagi barcha {"meta": {...}} havolalarni maqsad bazadagi mos
    obyektlarga almashtiradi. Mos topilmasa (masalan, biz ko'chirmaydigan tur:
    xodim, holat, fayl va h.k.) shu maydonni butunlay tashlab yuboradi, chunki
    manba akkauntdagi ID lar maqsad akkauntda hech narsani anglatmaydi."""
    if isinstance(node, dict):
        if set(node.keys()) == {"meta"}:
            href = (node.get("meta") or {}).get("href", "")
            parsed = parse_meta_href(href)
            if not parsed:
                return DROP
            kind = parsed[0]
            if kind == "entity":
                _, type_, old_id = parsed
                new_meta = maps["entity"].get(type_, {}).get(old_id)
                return {"meta": new_meta["meta"]} if new_meta else DROP
            if kind == "customentity":
                _, dict_id, elem_id = parsed
                new_meta = maps["customentity"].get(dict_id, {}).get(elem_id)
                return {"meta": new_meta["meta"]} if new_meta else DROP
            return DROP

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

import logging

from .attributes import migrate_attributes, resolve_attribute_values
from .entities import TOP_LEVEL_STRIP
from .mapper import parse_meta_href, resolve_refs
from .states import migrate_states

log = logging.getLogger("moysklad.documents")

# Hujjat turlari — tartib muhim: pozitsiyalarda ishlatiladigan tovarlar,
# omborlar, kontragentlar, tashkilotlar, shartnomalar oldin ko'chirilgan
# bo'lishi kerak (ENTITY_TYPES da). Buyurtmalar (order) yetkazib
# berish/jo'natishlardan oldin turadi, chunki demand/supply ularga orqaga
# havola qilishi mumkin. Qaytarishlar (return) o'zining asl hujjatidan
# (supply/demand) keyin turadi. To'lov hujjatlari eng oxirida, chunki ular
# demand/supply/invoice hujjatlariga havola qiladi ("operations").
#
# processingplan/processingorder/processing — "Производство" (texoperatsiya)
# moduli hujjatlari. Ularda "positions" o'rniga "materials"/"products" kabi
# alohida ro'yxatlar bor — bular ham "positions" kabi to'liq holda ro'yxat
# so'rovida QAYTMAYDI (faqat hajmi bilan meta-havola qaytadi), shuning uchun
# har biri uchun alohida sub-to'plam so'rovi kerak ("list_fields").
DOCUMENT_TYPES = [
    {"key": "enter", "path": "entity/enter", "has_attributes": True},
    {"key": "loss", "path": "entity/loss", "has_attributes": True},
    {"key": "move", "path": "entity/move", "has_attributes": True},
    {"key": "inventory", "path": "entity/inventory", "has_attributes": False},
    {
        "key": "processingplan",
        "path": "entity/processingplan",
        "has_attributes": False,
        "list_fields": ["materials", "products"],
    },
    {
        "key": "processingorder",
        "path": "entity/processingorder",
        "has_attributes": True,
        "list_fields": ["positions", "materials", "products"],
    },
    {
        "key": "processing",
        "path": "entity/processing",
        "has_attributes": True,
        "list_fields": ["materials", "products"],
    },
    {"key": "purchaseorder", "path": "entity/purchaseorder", "has_attributes": True},
    {"key": "supply", "path": "entity/supply", "has_attributes": True},
    {"key": "purchasereturn", "path": "entity/purchasereturn", "has_attributes": True},
    {"key": "customerorder", "path": "entity/customerorder", "has_attributes": True},
    {"key": "demand", "path": "entity/demand", "has_attributes": True},
    {"key": "salesreturn", "path": "entity/salesreturn", "has_attributes": True},
    {"key": "invoicein", "path": "entity/invoicein", "has_attributes": True},
    {"key": "invoiceout", "path": "entity/invoiceout", "has_attributes": True},
    {"key": "paymentin", "path": "entity/paymentin", "has_attributes": True},
    {"key": "paymentout", "path": "entity/paymentout", "has_attributes": True},
    {"key": "cashin", "path": "entity/cashin", "has_attributes": True},
    {"key": "cashout", "path": "entity/cashout", "has_attributes": True},
]

DOCUMENT_STRIP = TOP_LEVEL_STRIP | {"sum", "vatSum", "payedSum", "printed", "published"}
# "pack" — pozitsiyada tanlangan aniq qadoq (упаковка) variantiga havola;
# bu tovarning o'ziga (productga) emas, balki o'sha productning ICHKI,
# akkauntga xos qadoq yozuviga ishora qiladi va globalda qayta topilmaydi
# ("goodpack" turi), shuning uchun uni saqlab qolmaymiz.
POSITION_STRIP = {"id", "accountId", "meta", "pack"}


def fetch_list_field(client, doc_type: str, doc_id: str, field_name: str) -> list:
    rows = client.get_all(f"entity/{doc_type}/{doc_id}/{field_name}")
    return [{k: v for k, v in row.items() if k not in POSITION_STRIP} for row in rows]


def prepare_document_item(
    source_client, item: dict, doc_type: str, maps: dict, list_fields=("positions",)
) -> dict:
    cleaned = {k: v for k, v in item.items() if k not in DOCUMENT_STRIP}
    cleaned["externalCode"] = item["id"]

    for field in list_fields:
        if field in cleaned:
            cleaned[field] = fetch_list_field(source_client, doc_type, item["id"], field)

    attrs = cleaned.pop("attributes", None)
    resolved = resolve_refs(cleaned, maps)
    if attrs:
        new_attrs = resolve_attribute_values(attrs, doc_type, maps)
        if new_attrs:
            resolved["attributes"] = new_attrs

    # Maqsad bazaning hisob (учётная) valyutasi uchun kurs har doim 1
    # bo'lishi shart — manbadan boshqacha qiymat kelsa, MoySklad rad etadi.
    # Shu valyutaga tegishli bo'lsa, "rate"ni butunlay olib tashlaymiz —
    # MoySklad avtomatik 1 deb oladi.
    rate = resolved.get("rate")
    if isinstance(rate, dict):
        currency_href = ((rate.get("currency") or {}).get("meta") or {}).get("href", "")
        parsed = parse_meta_href(currency_href)
        if parsed and parsed[0] == "entity" and parsed[2] == maps.get("base_currency_id"):
            resolved.pop("rate", None)

    return resolved


def migrate_document_type(source_client, dest_client, cfg: dict, maps: dict, dry_run: bool = False):
    key = cfg["key"]
    path = cfg["path"]
    log.info("=== hujjat: %s ===", key)

    if not dry_run:
        migrate_states(source_client, dest_client, key, maps, dry_run=dry_run)
        if cfg.get("has_attributes"):
            migrate_attributes(source_client, dest_client, key, maps)

    source_items = source_client.get_all(path)
    log.info("%s: manbada %d ta hujjat topildi", key, len(source_items))

    id_map = maps["entity"].setdefault(key, {})
    if not source_items:
        return

    dest_items = dest_client.get_all(path)
    dest_by_ext = {d.get("externalCode"): d for d in dest_items if d.get("externalCode")}

    already = 0
    for item in source_items:
        existing = dest_by_ext.get(item["id"])
        if existing:
            id_map[item["id"]] = {"meta": existing["meta"]}
            already += 1

    remaining = [item for item in source_items if item["id"] not in id_map]
    remaining.sort(key=lambda x: x.get("moment", ""))
    log.info("%s: %d ta allaqachon mavjud, %d ta yaratiladi", key, already, len(remaining))

    if dry_run or not remaining:
        return

    list_fields = cfg.get("list_fields", ["positions"])
    for item in remaining:
        payload = prepare_document_item(source_client, item, key, maps, list_fields=list_fields)
        try:
            created = dest_client.post(path, payload)
        except RuntimeError as exc:
            log.error("%s: hujjat yaratilmadi (id=%s, nomi=%s): %s", key, item["id"], item.get("name"), exc)
            continue
        id_map[item["id"]] = {"meta": created["meta"]}

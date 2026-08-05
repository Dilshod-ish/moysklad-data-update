import logging
import re

log = logging.getLogger("moysklad.reschedule")

_RE_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})")

# Har bir hujjat turi uchun kunlik "maqsad" vaqt (soat:daqiqa). Sana
# o'zgarmaydi — faqat shu sanadagi vaqt shu jadvalga moslashtiriladi.
# Mantiq: avval tovar keladi (ombor to'ladi), keyin ishlab chiqariladi,
# kun oxirida sotiladi/chiqariladi — shunda qoldiq hech qachon vaqtinchalik
# "manfiy" bo'lib ko'rinmaydi.
TIME_SCHEDULE = {
    "inventory": "06:00",
    "enter": "06:30",
    "purchaseorder": "07:00",
    "supply": "08:00",
    "invoicein": "08:15",
    "purchasereturn": "09:00",
    "move": "09:30",
    "processingplan": "10:00",
    "processingorder": "10:00",
    "processing": "10:00",
    "customerorder": "11:00",
    "paymentin": "14:00",
    "cashin": "14:00",
    "loss": "19:00",
    "demand": "21:00",
    "invoiceout": "21:15",
    "salesreturn": "21:30",
    "paymentout": "22:00",
    "cashout": "22:00",
}


def new_moment_for(moment: str, time_str: str):
    """Sanani saqlab, vaqtni time_str ("HH:MM") bilan almashtiradi.
    moment tanib bo'lmasa None qaytaradi."""
    m = _RE_DATE.match(moment or "")
    if not m:
        return None
    return f"{m.group(1)} {time_str}:00"


def reschedule_type(client, doc_type: str, time_str: str, dry_run: bool = False):
    """Bitta hujjat turi uchun barcha hujjatlarning vaqtini to'g'irlaydi.
    (total, o'zgargan) ni qaytaradi."""
    items = client.get_all(f"entity/{doc_type}")
    updates = []
    for item in items:
        new_moment = new_moment_for(item.get("moment", ""), time_str)
        if new_moment and new_moment != item.get("moment"):
            updates.append({"id": item["id"], "meta": item["meta"], "moment": new_moment})

    log.info("%s: %d ta hujjatdan %d tasi vaqti o'zgaradi", doc_type, len(items), len(updates))

    if updates and not dry_run:
        client.bulk_update(f"entity/{doc_type}", updates)

    return len(items), len(updates)


def run(client, only=None, dry_run: bool = False):
    summary = {}
    for doc_type, time_str in TIME_SCHEDULE.items():
        if only and doc_type not in only:
            continue
        log.info("=== %s (maqsad vaqt: %s) ===", doc_type, time_str)
        try:
            total, changed = reschedule_type(client, doc_type, time_str, dry_run=dry_run)
            summary[doc_type] = changed
        except Exception as exc:  # noqa: BLE001
            log.error("%s: tuzatilmadi: %s", doc_type, exc)
            summary[doc_type] = None
    return summary

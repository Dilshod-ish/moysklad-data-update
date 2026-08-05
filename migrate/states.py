import logging

log = logging.getLogger("moysklad.states")


def migrate_states(source_client, dest_client, doc_type: str, maps: dict, dry_run: bool = False):
    """doc_type uchun hujjat holatlarini (status: Yangi, Yuborildi, Bajarildi
    va h.k.) nomi bo'yicha moslashtiradi, yo'q bo'lganlarini yaratadi."""
    source_meta = source_client.get(f"entity/{doc_type}/metadata")
    source_states = source_meta.get("states", [])
    if not source_states:
        return

    dest_meta = dest_client.get(f"entity/{doc_type}/metadata")
    dest_states = list(dest_meta.get("states", []))
    dest_by_name = {s["name"]: s for s in dest_states}

    missing = [s for s in source_states if s["name"] not in dest_by_name]
    if missing and not dry_run:
        for s in missing:
            dest_states.append(
                {"name": s["name"], "color": s.get("color"), "stateType": s.get("stateType")}
            )
        updated_meta = dest_client.put(f"entity/{doc_type}/metadata", {"states": dest_states})
        dest_states = updated_meta.get("states", dest_states)
        dest_by_name = {s["name"]: s for s in dest_states}

    state_map = maps["state"].setdefault(doc_type, {})
    for s in source_states:
        dest_state = dest_by_name.get(s["name"])
        if dest_state:
            state_map[s["id"]] = {"meta": dest_state["meta"]}

import logging
import time
from typing import Any, Optional

import requests

from .config import Credentials

log = logging.getLogger("moysklad.client")

PAGE_LIMIT = 1000
BATCH_SIZE = 100
MAX_RETRIES = 6
INTER_REQUEST_DELAY = 0.2  # rate limitga tegib qolmaslik uchun kichik pauza


class MoySkladClient:
    def __init__(self, creds: Credentials):
        self.base_url = creds.base_url.rstrip("/")
        self.session = requests.Session()
        if creds.token:
            self.session.headers["Authorization"] = f"Bearer {creds.token}"
        else:
            self.session.auth = (creds.login, creds.password)
        self.session.headers["Accept-Encoding"] = "gzip"
        self.session.headers["Content-Type"] = "application/json"

    def _url(self, path: str) -> str:
        return path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = self._url(path)
        last_exc: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.request(method, url, timeout=60, **kwargs)
            except requests.RequestException as exc:
                last_exc = exc
                wait = min(2 ** attempt, 30)
                log.warning("Tarmoq xatosi (%s), %ss dan keyin qayta urinish: %s", method, wait, exc)
                time.sleep(wait)
                continue

            if resp.status_code == 429:
                wait_ms = int(resp.headers.get("X-Lognex-Retry-After", "2000"))
                log.warning("Rate limitga tegib qoldik, %sms kutamiz", wait_ms)
                time.sleep(wait_ms / 1000)
                continue
            if resp.status_code >= 500:
                wait = min(2 ** attempt, 30)
                log.warning("Server xatosi %s, %ss dan keyin qayta urinish", resp.status_code, wait)
                time.sleep(wait)
                continue
            if not resp.ok:
                raise RuntimeError(f"{method} {url} -> {resp.status_code}: {resp.text[:800]}")

            time.sleep(INTER_REQUEST_DELAY)
            return resp

        raise RuntimeError(f"{method} {url}: {MAX_RETRIES} urinishdan keyin ham muvaffaqiyatsiz ({last_exc})")

    def get(self, path: str, params: Optional[dict] = None) -> Any:
        return self._request("GET", path, params=params).json()

    def get_all(self, path: str, params: Optional[dict] = None) -> list:
        params = dict(params or {})
        params["limit"] = PAGE_LIMIT
        offset = 0
        rows: list = []
        while True:
            params["offset"] = offset
            data = self._request("GET", path, params=params).json()
            batch = data.get("rows", []) if isinstance(data, dict) else data
            if not batch:
                break
            rows.extend(batch)
            size = data.get("meta", {}).get("size", len(rows)) if isinstance(data, dict) else len(rows)
            offset += PAGE_LIMIT
            if offset >= size:
                break
        return rows

    def post(self, path: str, payload) -> Any:
        return self._request("POST", path, json=payload).json()

    def put(self, path: str, payload) -> Any:
        return self._request("PUT", path, json=payload).json()

    def bulk_create(self, path: str, items: list) -> list:
        created: list = []
        for i in range(0, len(items), BATCH_SIZE):
            chunk = items[i : i + BATCH_SIZE]
            if not chunk:
                continue
            try:
                created.extend(self.post(path, chunk))
            except RuntimeError as exc:
                log.error("Batch yaratishda xato, elementlarni birma-bir urinamiz: %s", exc)
                for item in chunk:
                    try:
                        created.append(self.post(path, item))
                    except RuntimeError as item_exc:
                        log.error(
                            "Element yaratilmadi (externalCode=%s): %s",
                            item.get("externalCode"),
                            item_exc,
                        )
        return created

    def bulk_update(self, path: str, items: list) -> list:
        updated: list = []
        for i in range(0, len(items), BATCH_SIZE):
            chunk = items[i : i + BATCH_SIZE]
            if not chunk:
                continue
            try:
                updated.extend(self.put(path, chunk))
            except RuntimeError as exc:
                log.error("Batch yangilashda xato, elementlarni birma-bir urinamiz: %s", exc)
                for item in chunk:
                    try:
                        updated.append(self.put(path, item))
                    except RuntimeError as item_exc:
                        log.error(
                            "Element yangilanmadi (id=%s): %s",
                            (item.get("meta") or {}).get("href"),
                            item_exc,
                        )
        return updated

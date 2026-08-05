import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Credentials:
    base_url: str
    token: Optional[str]
    login: Optional[str]
    password: Optional[str]


def _creds(prefix: str) -> Credentials:
    return Credentials(
        base_url=os.environ.get(f"{prefix}_BASE_URL", "https://api.moysklad.ru/api/remap/1.2"),
        token=os.environ.get(f"{prefix}_TOKEN") or None,
        login=os.environ.get(f"{prefix}_LOGIN") or None,
        password=os.environ.get(f"{prefix}_PASSWORD") or None,
    )


def load_config():
    from dotenv import load_dotenv

    load_dotenv()

    source = _creds("SOURCE")
    dest = _creds("DEST")

    if not (source.token or (source.login and source.password)):
        raise RuntimeError(
            "Manba baza uchun autentifikatsiya topilmadi: .env faylida SOURCE_TOKEN "
            "yoki SOURCE_LOGIN+SOURCE_PASSWORD ni to'ldiring."
        )
    if not (dest.token or (dest.login and dest.password)):
        raise RuntimeError(
            "Maqsad baza uchun autentifikatsiya topilmadi: .env faylida DEST_TOKEN "
            "yoki DEST_LOGIN+DEST_PASSWORD ni to'ldiring."
        )
    return source, dest

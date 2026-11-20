import os
from pathlib import Path
import re
from urllib.parse import urlsplit


ADDRESS = re.compile(r"[a-z0-9][a-z0-9_.+-]{0,63}@([a-z0-9-]+(?:\.[a-z0-9-]+)+)\Z")
DOMAIN = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+\Z")
ROOT = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("DATA_DIR", ROOT / "data")) / "practice.sqlite3"
DOMAIN_NAME = os.environ.get("PORTAL_DOMAIN", "corp.example.test").strip().lower()
ORIGIN = os.environ.get("PORTAL_ORIGIN", "http://127.0.0.1:8080").rstrip("/")
origin_parts = urlsplit(ORIGIN)
if (
    not origin_parts.hostname or origin_parts.username or origin_parts.password
    or origin_parts.path or origin_parts.query or origin_parts.fragment
    or not (origin_parts.scheme == "https" or (
        origin_parts.scheme == "http" and origin_parts.hostname in {"localhost", "127.0.0.1", "::1"}
    ))
):
    raise ValueError("PORTAL_ORIGIN: укажите внутренний HTTPS-адрес или локальный HTTP-адрес.")
if not DOMAIN.fullmatch(DOMAIN_NAME):
    raise ValueError("PORTAL_DOMAIN: укажите корпоративный почтовый домен.")
AUTHORITY = origin_parts.netloc.lower()
SECURE_COOKIE = origin_parts.scheme == "https"


def normalize_address(address):
    if not isinstance(address, str):
        return None
    address = address.strip().lower()
    match = ADDRESS.fullmatch(address)
    return address if match and match[1] == DOMAIN_NAME else None

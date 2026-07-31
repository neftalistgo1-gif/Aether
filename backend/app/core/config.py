import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://aether:aether@localhost:5432/aether",
)
AETHER_POSTAL_CODES_PATH = os.getenv(
    "AETHER_POSTAL_CODES_PATH",
    str(BACKEND_DIR.parent / "docs" / "journal" / "codigos_postales.json"),
)

def bounded_integer_setting(
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


AETHER_BOOTSTRAP_SECRET = os.getenv("AETHER_BOOTSTRAP_SECRET")
AUTH_SESSION_HOURS = bounded_integer_setting(
    "AUTH_SESSION_HOURS",
    default=12,
    minimum=1,
    maximum=168,
)

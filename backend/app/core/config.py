import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")


def optional_setting(name: str) -> str | None:
    """Read an optional setting, treating blank values as not configured."""
    value = os.getenv(name)
    if value is None:
        return None
    return value.strip() or None


def secret_setting(name: str) -> str | None:
    """Read a secret from NAME_FILE or NAME without keeping blank secrets."""
    secret_file = optional_setting(f"{name}_FILE")
    if secret_file is not None:
        try:
            value = Path(secret_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"Unable to read secret file for {name}") from exc
        return value or None
    return optional_setting(name)


def database_url_setting() -> str:
    explicit_url = optional_setting("DATABASE_URL")
    if explicit_url is not None:
        return explicit_url

    password = secret_setting("DATABASE_PASSWORD")
    if password is None:
        return "postgresql+psycopg://aether:aether@localhost:5432/aether"

    username = optional_setting("DATABASE_USER") or "aether"
    host = optional_setting("DATABASE_HOST") or "localhost"
    port = optional_setting("DATABASE_PORT") or "5432"
    database = optional_setting("DATABASE_NAME") or "aether"
    return (
        "postgresql+psycopg://"
        f"{quote_plus(username)}:{quote_plus(password)}@{host}:{port}/"
        f"{quote_plus(database)}"
    )


DATABASE_URL = database_url_setting()
PRIVATE_STORAGE_DIR = Path(
    optional_setting("AETHER_PRIVATE_STORAGE_PATH")
    or BACKEND_DIR / "private_storage"
)
AETHER_POSTAL_CODES_PATH = os.getenv(
    "AETHER_POSTAL_CODES_PATH",
    str(PRIVATE_STORAGE_DIR / "postal_codes.json"),
)
CONTRACT_TEMPLATE_PATH = Path(os.getenv(
    "AETHER_CONTRACT_TEMPLATE_PATH",
    str(PRIVATE_STORAGE_DIR / "contract_templates" / "contrato_maestro.docx"),
))
CONTRACT_DOCUMENTS_PATH = Path(os.getenv(
    "AETHER_CONTRACT_DOCUMENTS_PATH",
    str(PRIVATE_STORAGE_DIR / "contracts"),
))


def boolean_setting(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

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


AETHER_BOOTSTRAP_SECRET = secret_setting("AETHER_BOOTSTRAP_SECRET")
if AETHER_BOOTSTRAP_SECRET is not None and len(AETHER_BOOTSTRAP_SECRET) < 32:
    raise RuntimeError("AETHER_BOOTSTRAP_SECRET must contain at least 32 characters")
AUTH_SESSION_HOURS = bounded_integer_setting(
    "AUTH_SESSION_HOURS",
    default=12,
    minimum=1,
    maximum=168,
)
UISP_ENDPOINT_URL = optional_setting("UISP_ENDPOINT_URL")
UISP_API_TOKEN = secret_setting("UISP_API_TOKEN")
UISP_TIMEOUT_SECONDS = bounded_integer_setting(
    "UISP_TIMEOUT_SECONDS",
    default=15,
    minimum=3,
    maximum=60,
)
UISP_VERIFY_TLS = boolean_setting("UISP_VERIFY_TLS", default=True)
UISP_SERVICE_REFERENCE_PATH = os.getenv(
    "UISP_SERVICE_REFERENCE_PATH",
    str(PRIVATE_STORAGE_DIR / "uisp_reference" / "services.json"),
)

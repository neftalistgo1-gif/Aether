import base64
import hashlib
import hmac
import secrets
from contextvars import ContextVar, Token
from dataclasses import dataclass
from uuid import UUID


SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_LENGTH = 64


@dataclass(frozen=True)
class AuthenticatedActor:
    user_id: UUID
    display_name: str
    source_ip: str | None = None
    device: str | None = None


_authenticated_actor: ContextVar[AuthenticatedActor | None] = ContextVar(
    "authenticated_actor",
    default=None,
)


def current_authenticated_actor() -> AuthenticatedActor | None:
    return _authenticated_actor.get()


def set_authenticated_actor(actor: AuthenticatedActor) -> Token:
    return _authenticated_actor.set(actor)


def reset_authenticated_actor(token: Token) -> None:
    _authenticated_actor.reset(token)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_LENGTH,
    )
    return "$".join(
        (
            "scrypt",
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(derived).decode("ascii"),
        )
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_text, hash_text = encoded.split("$")
        if algorithm != "scrypt":
            return False
        parsed_n = int(n)
        parsed_r = int(r)
        parsed_p = int(p)
        if (parsed_n, parsed_r, parsed_p) != (
            SCRYPT_N,
            SCRYPT_R,
            SCRYPT_P,
        ):
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(hash_text.encode("ascii"))
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=parsed_n,
            r=parsed_r,
            p=parsed_p,
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def generate_session_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hash_session_token(token)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

"""argon2id hashing and password policy (spec §6.4)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.common.errors import validation_error

# argon2-cffi defaults (RFC 9106 "low memory" profile): time_cost=3, memory_cost=64 MiB, parallelism=4.
# These exceed the OWASP minimum (19 MiB, 2 iterations, 1 lane).
_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("devcommons-dummy-password-for-timing")

MIN_LEN = 10
MAX_LEN = 128


@lru_cache(maxsize=1)
def _common_passwords() -> frozenset[str]:
    path = Path(__file__).parent / "data" / "common_passwords.txt"
    try:
        return frozenset(line.strip().lower() for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except FileNotFoundError:  # pragma: no cover
        return frozenset()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Constant-ish time verification. A None hash verifies against a dummy so timing matches."""
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def password_problem(password: str, email: str | None = None, username: str | None = None) -> str | None:
    if len(password) < MIN_LEN:
        return f"Password must be at least {MIN_LEN} characters."
    if len(password) > MAX_LEN:
        return f"Password must be at most {MAX_LEN} characters."
    lowered = password.lower()
    if lowered in _common_passwords():
        return "This password is too common. Choose something less guessable."
    if email and lowered == email.lower():
        return "Password must not be the same as your email."
    if username and lowered == username.lower():
        return "Password must not be the same as your username."
    return None


def check_password_policy(password: str, email: str | None = None, username: str | None = None, field: str = "password"):
    problem = password_problem(password, email, username)
    if problem:
        raise validation_error({field: problem})

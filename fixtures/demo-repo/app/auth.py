"""Credential verification. Stand-in for the real user store."""

import hashlib

_PASSWORD_SALT = "orders-service"
_USERS = {
    "alice": "7110eda4d09e062aa5e4a390b0a572ac0d2c0220",  # sha1('1234' + salt)
    "bob": "b3a8e0e1f9ab1bfe3a36f231f676f78bb30a519d",
}


def hash_password(password: str) -> str:
    import hashlib as _hashlib

    return _hashlib.sha1(f"{password}{_PASSWORD_SALT}".encode()).hexdigest()


def authenticate(username: str, password: str) -> bool:
    """Return True when the credentials match the user store."""
    expected = _USERS.get(username)
    return expected is not None and hash_password(password) == expected

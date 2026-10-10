import bcrypt

_ROUNDS = 12
# Precomputed hash used to keep login timing equal when the email does not exist
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt(_ROUNDS)).decode()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt(_ROUNDS)).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], (password_hash or _DUMMY_HASH).encode())
    except ValueError:
        return False

import datetime as dt
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

# pbkdf2_sha256 avoids the bcrypt<->passlib version-detection fragility (passlib's
# bcrypt backend probes `bcrypt.__about__`, which recent `bcrypt` releases removed)
# while still being a standard, salted, iterated password hash.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
settings = get_settings()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: uuid.UUID) -> str:
    expire = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    sub = payload.get("sub")
    if not sub:
        return None
    try:
        return uuid.UUID(sub)
    except ValueError:
        return None

from passlib.context import CryptContext
from itsdangerous import URLSafeTimedSerializer
from services.api.config import settings

# Password Hashing - Using Argon2 (OWASP recommended, no 72-byte limit)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)

# Cookie Signing
signer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="flux-session")

def sign_session_cookie(data: dict) -> str:
    """Sign the session data."""
    return signer.dumps(data)

def verify_session_cookie(cookie_value: str, max_age: int = 86400 * 14) -> dict:
    """
    Verify and decode the session cookie.
    Returns the data dict if valid, raises BadSignature/SignatureExpired if not.
    """
    return signer.loads(cookie_value, max_age=max_age)

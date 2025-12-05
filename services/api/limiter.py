from slowapi import Limiter
from slowapi.util import get_remote_address

# Initialize Limiter
# Uses remote address (IP) as the key for rate limiting
limiter = Limiter(key_func=get_remote_address)

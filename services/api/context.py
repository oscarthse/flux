from contextvars import ContextVar
from typing import Optional

# Context variable to store the current tenant ID for the request
tenant_context: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID

class NormalizedLineItem(BaseModel):
    external_id: str
    name: str
    quantity: int
    price: float
    modifiers: List[str] = []

class NormalizedOrder(BaseModel):
    external_id: str
    timestamp: datetime
    source: str
    party_size: Optional[int] = 1
    total_amount: float
    items: List[NormalizedLineItem]

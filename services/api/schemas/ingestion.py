from pydantic import BaseModel, Field, validator
from typing import List, Optional
from enum import Enum
from decimal import Decimal
from datetime import date, datetime

class IngestionSource(str, Enum):
    SQUARE = "square"
    TOAST = "toast"
    CSV = "csv"

class CategoryEnum(str, Enum):
    BURGERS = "Burgers"
    SIDES = "Sides"
    BEVERAGES = "Beverages"
    APPETIZERS = "Appetizers"
    DESSERTS = "Desserts"
    ALCOHOL = "Alcohol"
    OTHER = "Other"

class IngredientRow(BaseModel):
    name: str = Field(..., max_length=100)
    cost_per_unit: Decimal = Field(..., ge=0)
    unit: str = Field(..., max_length=20)
    par_level: Decimal = Field(..., ge=0)
    reorder_threshold: Decimal = Field(..., ge=0)
    lead_time_days: int = Field(..., ge=0)
    shelf_life_days: int = Field(..., ge=0)

class MenuRow(BaseModel):
    name: str = Field(..., max_length=100)
    category: Optional[str] = Field("Other", max_length=50)
    price: Decimal = Field(..., ge=0)

class RecipeRow(BaseModel):
    menu_item: str = Field(..., max_length=100)
    ingredient: str = Field(..., max_length=100)
    quantity: Decimal = Field(..., gt=0)

class SalesRow(BaseModel):
    date: date
    menu_item: str = Field(..., max_length=100)
    quantity: int = Field(..., ge=0)

class ValidationResult(BaseModel):
    status: str
    errors: List[str] = []
    warnings: List[str] = []
    records_processed: int = 0

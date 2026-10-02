from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CustomerProfile(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    preferences: Dict[str, Any] = Field(default_factory=dict)


class OrderItem(BaseModel):
    name: str
    quantity: int = 1
    unit_price: int
    total_price: int
    details: Dict[str, Any] = Field(default_factory=dict)


class OrderData(BaseModel):
    customer_name: str
    whatsapp_number: str
    delivery_phone: Optional[str] = None
    address: str

    food_items: List[OrderItem] = Field(default_factory=list)
    drinks: List[OrderItem] = Field(default_factory=list)

    payment_method: str

    subtotal: int
    discount: int = 0
    total: int

    preferences: Dict[str, Any] = Field(default_factory=dict)


class AIResult(BaseModel):
    reply: str
    intent: str = "conversation"

    customer_name: Optional[str] = None
    address: Optional[str] = None
    delivery_phone: Optional[str] = None

    food_items: List[Dict[str, Any]] = Field(default_factory=list)
    drinks: List[Dict[str, Any]] = Field(default_factory=list)

    payment_method: Optional[str] = None
    preferences: Dict[str, Any] = Field(default_factory=dict)

    confirmed: bool = False
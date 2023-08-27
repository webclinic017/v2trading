from enum import Enum
from datetime import datetime
from pydantic import BaseModel
from typing import Any, Optional, List, Union
from uuid import UUID
class TradeStatus(str, Enum):
    READY = "ready"
    ACTIVATED = "activated"
    #FINISHED = "finished"

class TradeDirection(str, Enum):
    LONG = "long"
    SHORT = "short"

class TradeStoplossType(str, Enum):
    FIXED = "fixed"
    TRAILING = "trailing"

class Trade(BaseModel):
    id: UUID
    validfrom: datetime
    status: TradeStatus
    direction: TradeDirection
    entry_price: Optional[float] = None
    # stoploss_type: TradeStoplossType
    stoploss_value: Optional[float] = None
    profit: Optional[float] = None
    profit_sum: Optional[float] = None
    

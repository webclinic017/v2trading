from enum import Enum
from alpaca.trading.enums import OrderSide, OrderStatus
class Order:
    def __init__(self, id: str, status: OrderStatus, side: OrderSide, symbol: str, qty: int, limit_price: float = None, filled_qty: int = 0, filled_avg_price: float = 0, filled_time: float = None) -> None:
        self.id = id
        self.status = status
        self.side = side
        self.symbol = symbol
        self.qty = qty
        self.filled_qty = filled_qty
        self.filled_avg_price = filled_avg_price
        self.filled_time = filled_time 
        self.limit_price = limit_price


class FillCondition(str, Enum):
    """
    Execution settings:
        fast = pro vyplneni limi orderu musi byt cena stejne
        slow = vetsi (prip. mensi pro sell)
        TBD nejspis pridat jeste stredni cestu - musi byt stejna
    """
    FAST = "fast"
    SLOW = "slow"
class Account(str, Enum):
    """
    Accounts - keys to config
    """
    ACCOUNT1 = "ACCOUNT1"
    ACCOUNT2 = "ACCOUNT2"
class RecordType(str, Enum):
    """
    Represents output of aggregator
    """

    BAR = "bar"
    CBAR = "continuosbar"
    TRADE = "trade"

class Mode(str, Enum):
    """
    LIVE or BT
    """

    PAPER = "paper"
    LIVE = "live"
    BT = "backtest"


class StartBarAlign(str, Enum):
    """
    Represents first bar start time alignement according to timeframe
        ROUND = bar starts at 0,5,10 (for 5s timeframe)
        RANDOM = first bar starts when first trade occurs
    """ 
    ROUND = "round"
    RANDOM = "random"
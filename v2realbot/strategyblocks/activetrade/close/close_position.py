from v2realbot.strategy.base import StrategyState
from v2realbot.strategy.StrategyOrderLimitVykladaciNormalizedMYSELL import StrategyOrderLimitVykladaciNormalizedMYSELL
from v2realbot.enums.enums import RecordType, StartBarAlign, Mode, Account, Followup
from v2realbot.common.PrescribedTradeModel import Trade, TradeDirection, TradeStatus
from v2realbot.utils.utils import isrising, isfalling,zoneNY, price2dec, print, safe_get, is_still, is_window_open, eval_cond_dict, crossed_down, crossed_up, crossed, is_pivot, json_serial, pct_diff, create_new_bars, slice_dict_lists
from v2realbot.utils.directive_utils import get_conditions_from_configuration
from v2realbot.ml.mlutils import load_model
from v2realbot.common.model import SLHistory
from v2realbot.config import KW
from uuid import uuid4
from datetime import datetime
#import random
import json
import numpy as np
#from icecream import install, ic
from rich import print as printanyway
from threading import Event
import os
from traceback import format_exc
from v2realbot.strategyblocks.activetrade.helpers import insert_SL_history

# - close means change status in prescribed Trends,update profit, delete from activeTrade
def close_position(state, data, direction: TradeDirection, reason: str, followup: Followup = None):
    followup_text = str(followup) if followup is not None else ""
    state.ilog(lvl=1,e=f"CLOSING TRADE {followup_text} {reason} {str(direction)}", curr_price=data["close"], trade=state.vars.activeTrade)
    if direction == TradeDirection.SHORT:
        res = state.buy(size=abs(int(state.positions)))
        if isinstance(res, int) and res < 0:
            raise Exception(f"error in required operation {reason} {res}")

    elif direction == TradeDirection.LONG:
        res = state.sell(size=state.positions)
        if isinstance(res, int) and res < 0:
            raise Exception(f"error in required operation STOPLOSS SELL {res}")
    
    else:
        raise Exception(f"unknow TradeDirection in close_position")
    
    #pri uzavreni tradu zapisujeme SL history - lepsi zorbazeni v grafu
    insert_SL_history(state)
    state.dont_exit_already_activated = False
    state.vars.pending = state.vars.activeTrade.id
    state.vars.activeTrade = None   
    state.vars.last_exit_index = data["index"]    
    if followup is not None:
        state.vars.requested_followup = followup

#close only partial position - no followup here, size multiplier must be between 0 and 1
def close_position_partial(state, data, direction: TradeDirection, reason: str, size: float):
    if size <= 0 or size >=1:
        raise Exception(f"size must be betweem 0 and 1")
    size_abs = abs(int(int(state.positions)*size))
    state.ilog(lvl=1,e=f"CLOSING TRADE PART: {size_abs} {size} {reason} {str(direction)}", curr_price=data["close"], trade=state.vars.activeTrade)
    if direction == TradeDirection.SHORT:
        res = state.buy(size=size_abs)
        if isinstance(res, int) and res < 0:
            raise Exception(f"error in required operation STOPLOSS PARTIAL BUY {reason} {res}")

    elif direction == TradeDirection.LONG:
        res = state.sell(size=size_abs)
        if isinstance(res, int) and res < 0:
            raise Exception(f"error in required operation STOPLOSS PARTIAL SELL {res}")
    else:
        raise Exception(f"unknow TradeDirection in close_position")
    
    #pri uzavreni tradu zapisujeme SL history - lepsi zorbazeni v grafu
    insert_SL_history(state)
    state.vars.pending = state.vars.activeTrade.id
    #state.vars.activeTrade = None   
    #state.vars.last_exit_index = data["index"]    
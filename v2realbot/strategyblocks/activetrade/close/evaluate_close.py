from v2realbot.strategyblocks.activetrade.close.close_position import close_position, close_position_partial
from v2realbot.strategy.base import StrategyState
from v2realbot.enums.enums import  Followup
from v2realbot.common.PrescribedTradeModel import Trade, TradeDirection, TradeStatus
from v2realbot.utils.utils import safe_get
from v2realbot.config import KW
#from icecream import install, ic
from rich import print as printanyway
from threading import Event
import os
from traceback import format_exc
from v2realbot.strategyblocks.activetrade.close.eod_exit import eod_exit_activated
from v2realbot.strategyblocks.activetrade.close.conditions import dontexit_protection_met, exit_conditions_met
from v2realbot.strategyblocks.activetrade.helpers import get_max_profit_price, get_profit_target_price, get_override_for_active_trade, keyword_conditions_met
from v2realbot.strategyblocks.activetrade.sl.optimsl import SLOptimizer

def eval_close_position(state: StrategyState, data):
    curr_price = float(data['close'])
    state.ilog(lvl=0,e="Eval CLOSE", price=curr_price, pos=state.positions, avgp=state.avgp, pending=state.vars.pending, activeTrade=str(state.vars.activeTrade))

    if int(state.positions) != 0 and float(state.avgp)>0 and state.vars.pending is None:
        
        #close position handling
        #TBD pridat OPTIMALIZACI POZICE - EXIT 1/2

        #mame short pozice - (IDEA: rozlisovat na zaklade aktivniho tradu - umozni mi spoustet i pri soucasne long pozicemi)
        if int(state.positions) < 0:
            #get TARGET PRICE pro dany smer a signal

            #pokud existujeme bereme z nastaveni tradu a nebo z defaultu
            if state.vars.activeTrade.goal_price is not None:
                 goal_price = state.vars.activeTrade.goal_price
            else:
                goal_price = get_profit_target_price(state, data, TradeDirection.SHORT)

            max_price = get_max_profit_price(state, data, TradeDirection.SHORT)
            state.ilog(lvl=1,e=f"Def Goal price {str(TradeDirection.SHORT)} {goal_price} max price {max_price}")                
            
            #SL OPTIMALIZATION - PARTIAL EXIT
            level_met, exit_adjustment = state.sl_optimizer_short.eval_position(state, data)
            if level_met is not None and exit_adjustment is not None:
                position = state.positions * exit_adjustment
                state.ilog(lvl=1,e=f"SL OPTIMIZATION ENGAGED {str(TradeDirection.SHORT)} {position=} {level_met=} {exit_adjustment}", initial_levels=str(state.sl_optimizer_short.get_initial_abs_levels(state)), rem_levels=str(state.sl_optimizer_short.get_remaining_abs_levels(state)), exit_levels=str(state.sl_optimizer_short.exit_levels), exit_sizes=str(state.sl_optimizer_short.exit_sizes))
                printanyway(f"SL OPTIMIZATION ENGAGED {str(TradeDirection.SHORT)} {position=} {level_met=} {exit_adjustment}")
                close_position_partial(state=state, data=data, direction=TradeDirection.SHORT, reason=F"SL OPT LEVEL {level_met} REACHED", size=exit_adjustment)
                return
            
            #FULL SL reached - execution
            if curr_price > state.vars.activeTrade.stoploss_value:

                directive_name = 'reverse_for_SL_exit_short'
                reverse_for_SL_exit = get_override_for_active_trade(state=state, directive_name=directive_name, default_value=safe_get(state.vars, directive_name, "no"))

                if reverse_for_SL_exit == "always":
                    followup_action = Followup.REVERSE
                elif reverse_for_SL_exit == "cond":
                    followup_action = Followup.REVERSE if keyword_conditions_met(state, data, direction=TradeDirection.SHORT, keyword=KW.slreverseonly, skip_conf_validation=True) else None
                else:
                    followup_action = None
                close_position(state=state, data=data, direction=TradeDirection.SHORT, reason="SL REACHED", followup=followup_action)
                return
                
            
            #REVERSE BASED ON REVERSE CONDITIONS
            if keyword_conditions_met(state, data, direction=TradeDirection.SHORT, keyword=KW.reverse):
                    close_position(state=state, data=data, direction=TradeDirection.SHORT, reason="REVERSE COND MET", followup=Followup.REVERSE)
                    return  

            #EXIT ADD CONDITIONS MET (exit and add)
            if keyword_conditions_met(state, data, direction=TradeDirection.SHORT, keyword=KW.exitadd):
                    close_position(state=state, data=data, direction=TradeDirection.SHORT, reason="EXITADD COND MET", followup=Followup.ADD)
                    return  

            #CLOSING BASED ON EXIT CONDITIONS
            if exit_conditions_met(state, data, TradeDirection.SHORT):
                    directive_name = 'reverse_for_cond_exit_short'
                    reverse_for_cond_exit_short = get_override_for_active_trade(state=state, directive_name=directive_name, default_value=safe_get(state.vars, directive_name, False))
                    directive_name = 'add_for_cond_exit_short'
                    add_for_cond_exit_short = get_override_for_active_trade(state=state, directive_name=directive_name, default_value=safe_get(state.vars, directive_name, False))
                    if reverse_for_cond_exit_short:
                        followup_action = Followup.REVERSE
                    elif add_for_cond_exit_short: 
                        followup_action = Followup.ADD
                    else:
                        followup_action = None
                    close_position(state=state, data=data, direction=TradeDirection.SHORT, reason="EXIT COND MET", followup=followup_action)
                    return                   

            #PROFIT
            if curr_price<=goal_price:
                #TODO cekat az slope prestane intenzivn erust, necekat az na klesani
                #TODO mozna cekat na nejaky signal RSI
                #TODO pripadne pokud dosahne TGTBB prodat ihned
                max_price_signal = curr_price<=max_price
                #OPTIMALIZACE pri stoupajícím angle
                if max_price_signal or dontexit_protection_met(state=state, data=data,direction=TradeDirection.SHORT) is False:
                    close_position(state=state, data=data, direction=TradeDirection.SHORT, reason=f"PROFIT or MAXPROFIT REACHED {max_price_signal=}")
                    return

            #FORCED EXIT PRI KONCI DNE
            if eod_exit_activated(state, data, TradeDirection.SHORT):
                    close_position(state=state, data=data, direction=TradeDirection.SHORT, reason="EOD EXIT ACTIVATED")
                    return           
               
        #mame long
        elif int(state.positions) > 0:

            #get TARGET PRICE pro dany smer a signal
            #pokud existujeme bereme z nastaveni tradu a nebo z defaultu
            if state.vars.activeTrade.goal_price is not None:
                 goal_price = state.vars.activeTrade.goal_price
            else:
                goal_price = get_profit_target_price(state, data, TradeDirection.LONG)
        
            max_price = get_max_profit_price(state, data, TradeDirection.LONG)
            state.ilog(lvl=1,e=f"Goal price {str(TradeDirection.LONG)} {goal_price} max price {max_price}")

            #SL OPTIMALIZATION - PARTIAL EXIT
            level_met, exit_adjustment = state.sl_optimizer_long.eval_position(state, data)
            if level_met is not None and exit_adjustment is not None:
                position = state.positions * exit_adjustment
                state.ilog(lvl=1,e=f"SL OPTIMIZATION ENGAGED {str(TradeDirection.LONG)} {position=} {level_met=} {exit_adjustment}", initial_levels=str(state.sl_optimizer_long.get_initial_abs_levels(state)), rem_levels=str(state.sl_optimizer_long.get_remaining_abs_levels(state)), exit_levels=str(state.sl_optimizer_long.exit_levels), exit_sizes=str(state.sl_optimizer_long.exit_sizes))
                printanyway(f"SL OPTIMIZATION ENGAGED {str(TradeDirection.LONG)} {position=} {level_met=} {exit_adjustment}")
                close_position_partial(state=state, data=data, direction=TradeDirection.LONG, reason=f"SL OPT LEVEL {level_met} REACHED", size=exit_adjustment)
                return

            #SL FULL execution
            if curr_price < state.vars.activeTrade.stoploss_value:
                directive_name = 'reverse_for_SL_exit_long'
                reverse_for_SL_exit = get_override_for_active_trade(state, directive_name=directive_name, default_value=safe_get(state.vars, directive_name, "no"))

                state.ilog(lvl=1, e=f"reverse_for_SL_exit {reverse_for_SL_exit}")

                if reverse_for_SL_exit == "always":
                    followup_action = Followup.REVERSE
                elif reverse_for_SL_exit == "cond":
                    followup_action = Followup.REVERSE if keyword_conditions_met(state, data, direction=TradeDirection.LONG, keyword=KW.slreverseonly, skip_conf_validation=True) else None
                else:
                    followup_action = None

                close_position(state=state, data=data, direction=TradeDirection.LONG, reason="SL REACHED", followup=followup_action)
                return
            

            #REVERSE BASED ON REVERSE CONDITIONS
            if keyword_conditions_met(state, data,TradeDirection.LONG, KW.reverse):
                    close_position(state=state, data=data, direction=TradeDirection.LONG, reason="REVERSE COND MET", followup=Followup.REVERSE)
                    return  

            #EXIT ADD CONDITIONS MET (exit and add)
            if keyword_conditions_met(state, data, TradeDirection.LONG, KW.exitadd):
                    close_position(state=state, data=data, direction=TradeDirection.LONG, reason="EXITADD COND MET", followup=Followup.ADD)
                    return  

            #EXIT CONDITIONS
            if exit_conditions_met(state, data, TradeDirection.LONG):
                    directive_name = 'reverse_for_cond_exit_long'
                    reverse_for_cond_exit_long = get_override_for_active_trade(state, directive_name=directive_name, default_value=safe_get(state.vars, directive_name, False))
                    directive_name = 'add_for_cond_exit_long'
                    add_for_cond_exit_long = get_override_for_active_trade(state, directive_name=directive_name, default_value=safe_get(state.vars, directive_name, False))
                    if reverse_for_cond_exit_long:
                        followup_action = Followup.REVERSE
                    elif add_for_cond_exit_long: 
                        followup_action = Followup.ADD
                    else:
                        followup_action = None
                    close_position(state=state, data=data, direction=TradeDirection.LONG, reason="EXIT CONDS MET", followup=followup_action)
                    return    

            #PROFIT
            if curr_price>=goal_price:
                #TODO cekat az slope prestane intenzivn erust, necekat az na klesani
                #TODO mozna cekat na nejaky signal RSI
                #TODO pripadne pokud dosahne TGTBB prodat ihned
                max_price_signal = curr_price>=max_price
                #OPTIMALIZACE pri stoupajícím angle
                if max_price_signal or dontexit_protection_met(state, data, direction=TradeDirection.LONG) is False:
                    close_position(state=state, data=data, direction=TradeDirection.LONG, reason=f"PROFIT or MAXPROFIT REACHED {max_price_signal=}")
                    return

            #FORCED EXIT PRI KONCI DNE
            if eod_exit_activated(state, data, TradeDirection.LONG):
                    close_position(state=state, data=data, direction=TradeDirection.LONG, reason="EOD EXIT ACTIVATED")
                    return      
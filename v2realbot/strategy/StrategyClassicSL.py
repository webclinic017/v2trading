from v2realbot.strategy.base import Strategy
from v2realbot.utils.utils import parse_alpaca_timestamp, ltp, AttributeDict,trunc,price2dec, zoneNY, print, json_serial, safe_get, get_tick, send_to_telegram
from v2realbot.utils.tlog import tlog, tlog_exception
from v2realbot.enums.enums import Mode, Order, Account, RecordType, Followup
#from alpaca.trading.models import TradeUpdate
from  v2realbot.common.model import TradeUpdate
from v2realbot.common.PrescribedTradeModel import Trade, TradeDirection, TradeStatus
from alpaca.trading.enums import TradeEvent, OrderStatus
from v2realbot.indicators.indicators import ema
import json
from datetime import datetime
#from rich import print
from random import randrange
from alpaca.common.exceptions import APIError
import numpy as np
from threading import Event
from uuid import UUID, uuid4
from v2realbot.strategyblocks.indicators.indicators_hub import populate_all_indicators
from v2realbot.strategyblocks.activetrade.helpers import get_profit_target_price

class StrategyClassicSL(Strategy):
    """
    Base override file for Classic Stop-Loss startegy
    """
    def __init__(self, name: str, symbol: str, next: callable, init: callable, account: Account, mode: Mode = Mode.PAPER, stratvars: AttributeDict = None, open_rush: int = 30, close_rush: int = 30, pe: Event = None, se: Event = None, runner_id: UUID = None, ilog_save: bool = False) -> None:
        super().__init__(name, symbol, next, init, account, mode, stratvars, open_rush, close_rush, pe, se, runner_id, ilog_save)

    #zkontroluje zda aktualni profit/loss - nedosahnul limit a pokud ano tak vypne strategii

    ##TODO zestručnit a dát pryč opakovací kód
    async def stop_when_max_profit_loss(self):
        self.state.ilog(e="CHECK MAX PROFIT")
        max_sum_profit_to_quit = safe_get(self.state.vars, "max_sum_profit_to_quit", None)
        max_sum_loss_to_quit = safe_get(self.state.vars, "max_sum_loss_to_quit", None)

        max_sum_profit_to_quit_rel = safe_get(self.state.vars, "max_sum_profit_to_quit_rel", None)
        max_sum_loss_to_quit_rel = safe_get(self.state.vars, "max_sum_loss_to_quit_rel", None)

        if max_sum_profit_to_quit_rel is not None:
            rel_profit  = round(float(np.mean(self.state.rel_profit_cum)),5)
            if rel_profit >= float(max_sum_profit_to_quit_rel):
                self.state.ilog(e=f"QUITTING MAX SUM REL PROFIT REACHED {max_sum_profit_to_quit_rel=} {self.state.profit=} {rel_profit=}")
                self.state.vars.pending = "max_sum_profit_to_quit_rel"
                send_to_telegram(f"QUITTING MAX SUM REL PROFIT REACHED {max_sum_profit_to_quit_rel=} {self.state.profit=} {rel_profit=}")
                self.se.set()
                return True
        if max_sum_loss_to_quit_rel is not None:
            rel_profit  = round(float(np.mean(self.state.rel_profit_cum)),5)
            if rel_profit < 0 and rel_profit <= float(max_sum_loss_to_quit_rel):
                self.state.ilog(e=f"QUITTING MAX SUM REL LOSS REACHED {max_sum_loss_to_quit_rel=} {self.state.profit=} {rel_profit=}")
                self.state.vars.pending = "max_sum_loss_to_quit_rel"
                send_to_telegram(f"QUITTING MAX SUM REL LOSS REACHED {max_sum_loss_to_quit_rel=} {self.state.profit=} {rel_profit=}")
                self.se.set()
                return True

        if max_sum_profit_to_quit is not None:
            if float(self.state.profit) >= float(max_sum_profit_to_quit):
                self.state.ilog(e=f"QUITTING MAX SUM ABS PROFIT REACHED {max_sum_profit_to_quit=} {self.state.profit=} {rel_profit=}")
                self.state.vars.pending = "max_sum_profit_to_quit"
                send_to_telegram(f"QUITTING MAX SUM ABS PROFIT REACHED {max_sum_profit_to_quit=} {self.state.profit=} {rel_profit=}")
                self.se.set()
                return True
        if max_sum_loss_to_quit is not None:
            if float(self.state.profit) < 0 and float(self.state.profit) <= float(max_sum_loss_to_quit):
                self.state.ilog(e=f"QUITTING MAX SUM ABS LOSS REACHED {max_sum_loss_to_quit=} {self.state.profit=} {rel_profit=}")
                self.state.vars.pending = "max_sum_loss_to_quit"
                send_to_telegram(f"QUITTING MAX SUM ABS LOSS REACHED {max_sum_loss_to_quit=} {self.state.profit=} {rel_profit=}")
                self.se.set()
                return True

        return False

    async def add_followup(self, direction: TradeDirection, size: int, signal_name: str):
        trade_to_add = Trade(
            id=uuid4(),
            last_update=datetime.fromtimestamp(self.state.time).astimezone(zoneNY),
            status=TradeStatus.READY,
            size=size,
            generated_by=signal_name,
            direction=direction,
            entry_price=None,
            stoploss_value = None)

        self.state.vars.prescribedTrades.append(trade_to_add)
        
        self.state.vars.requested_followup = None

        self.state.ilog(e=f"FOLLOWUP {direction} added to prescr.trades {signal_name=} {size=}", trade=trade_to_add)

    async def orderUpdateBuy(self, data: TradeUpdate):
        o: Order = data.order
        signal_name = None
        ##nejak to vymyslet, aby se dal poslat cely Trade a serializoval se
        self.state.ilog(e="Příchozí BUY notif", msg=o.status, trade=json.loads(json.dumps(data, default=json_serial)))

        if data.event == TradeEvent.FILL or data.event == TradeEvent.PARTIAL_FILL:

           #pokud jde o fill pred kterym je partail, muze se stat, ze uz budou vynulovany pozice, toto je pojistka
            #jde o uzavření short pozice - počítáme PROFIT
            if int(self.state.positions) < 0 or (int(self.state.positions) == 0 and self.state.wait_for_fill is not None):

                if data.event == TradeEvent.PARTIAL_FILL and self.state.wait_for_fill is None:
                    #timto si oznacime, ze po partialu s vlivem na PROFIT musime cekat na FILL a zaroven ukladame prum cenu, kterou potrebujeme na vypocet profitu u fillu
                    self.state.wait_for_fill = float(self.state.avgp)

                #PROFIT pocitame z TradeUpdate.price a TradeUpdate.qty - aktualne provedene mnozstvi a cena
                #naklady vypocteme z prumerne ceny, kterou mame v pozicich
                bought_amount = data.qty * data.price
                #podle prumerne vstupni ceny, kolik stalo toto mnozstvi
                if float(self.state.avgp) > 0:
                    vstup_cena = float(self.state.avgp)
                elif float(self.state.avgp) == 0 and self.state.wait_for_fill is not None:
                    vstup_cena = float(self.state.wait_for_fill)
                else:
                    vstup_cena = 0

                avg_costs = vstup_cena * float(data.qty)
                
                if avg_costs == 0:
                    self.state.ilog(e="ERR: Nemame naklady na PROFIT, AVGP je nula. Zaznamenano jako 0", msg="naklady=utrzena cena. TBD opravit.")
                    avg_costs = bought_amount

                trade_profit = round((avg_costs-bought_amount),2)
                self.state.profit += trade_profit

                rel_profit = 0
                #spoctene celkovy relativni profit za trade v procentech ((trade_profit/vstup_naklady)*100)
                if vstup_cena != 0 and int(data.order.qty) != 0:
                    rel_profit = round((trade_profit / (vstup_cena * float(data.order.qty))) * 100,5)

                #pokud jde o finalni FILL - pridame do pole tento celkovy relativnich profit (ze ktereho se pocita kumulativni relativni profit)
                rel_profit_cum_calculated = 0

                if data.event == TradeEvent.FILL:
                    #TODO pokud mame partial exit, tak se spravne vypocita relativni profit, ale
                    #  je jen na mensi mnozszvi take z nej delat cum_calculate je blbost - OPRAVIT
                    self.state.rel_profit_cum.append(rel_profit)
                    rel_profit_cum_calculated = round(np.mean(self.state.rel_profit_cum),5)

                self.state.ilog(e=f"BUY notif - SHORT PROFIT:{round(float(trade_profit),3)} celkem:{round(float(self.state.profit),3)} rel:{float(rel_profit)} rel_cum:{round(rel_profit_cum_calculated,7)}", msg=str(data.event), rel_profit_cum=str(self.state.rel_profit_cum), bought_amount=bought_amount, avg_costs=avg_costs, trade_qty=data.qty, trade_price=data.price, orderid=str(data.order.id))

                #zapsat profit do prescr.trades
                for trade in self.state.vars.prescribedTrades:
                    if trade.id == self.state.vars.pending:
                        trade.last_update = datetime.fromtimestamp(self.state.time).astimezone(zoneNY)
                        trade.profit += trade_profit
                        #pro ulozeni do tradeData scitame vsechen zisk z tohoto tradu (kvuli partialum)
                        trade_profit = trade.profit
                        trade.profit_sum = self.state.profit
                        trade.rel_profit = rel_profit
                        trade.rel_profit_cum = rel_profit_cum_calculated
                        signal_name = trade.generated_by
                        if data.event == TradeEvent.FILL:
                            trade.status == TradeStatus.CLOSED
                        break

                if data.event == TradeEvent.FILL:
                    #mazeme self.state.
                    self.state.wait_for_fill = None
                    #zapsat update profitu do tradeList
                    for tradeData in self.state.tradeList:
                        if tradeData.execution_id == data.execution_id:
                            #pridat jako attribut, aby proslo i na LIVE a PAPPER, kde se bere TradeUpdate z Alpaca
                            setattr(tradeData, "profit", trade_profit)
                            setattr(tradeData, "profit_sum", self.state.profit)
                            setattr(tradeData, "signal_name", signal_name)
                            #self.state.ilog(f"updatnut tradeList o profit", tradeData=json.loads(json.dumps(tradeData, default=json_serial)))
                            setattr(tradeData, "rel_profit", rel_profit)
                            setattr(tradeData, "rel_profit_cum", rel_profit_cum_calculated)

                #test na maximalni profit/loss, pokud vypiname pak uz nedelame pripdany reverzal
                if await self.stop_when_max_profit_loss() is False:

                    #pIF REVERSAL REQUIRED - reverse position is added to prescr.Trades with same signal name
                    #jen při celém FILLU
                    if data.event == TradeEvent.FILL and self.state.vars.requested_followup is not None:
                            if self.state.vars.requested_followup == Followup.REVERSE:
                                await self.add_followup(direction=TradeDirection.LONG, size=o.qty, signal_name=signal_name)
                            elif self.state.vars.requested_followup == Followup.ADD:
                                #zatim stejna SIZE
                                await self.add_followup(direction=TradeDirection.SHORT, size=o.qty, signal_name=signal_name)
            else:
                #zjistime nazev signalu a updatneme do tradeListu - abychom meli svazano
                for trade in self.state.vars.prescribedTrades:
                    if trade.id == self.state.vars.pending:
                        signal_name = trade.generated_by

                #zapsat do tradeList
                for tradeData in self.state.tradeList:
                    if tradeData.execution_id == data.execution_id:
                        setattr(tradeData, "signal_name", signal_name)

                self.state.ilog(e="BUY: Jde o LONG nakuú nepocitame profit zatim")

                if data.event == TradeEvent.FILL:
                    #zapisujeme last entry price
                    self.state.last_entry_price["long"] = data.price

                    #pokud neni nastaveno goal_price tak vyplnujeme defaultem
                    if self.state.vars.activeTrade.goal_price is None:
                        dat = dict(close=data.price)
                        self.state.vars.activeTrade.goal_price = get_profit_target_price(self.state, dat, TradeDirection.LONG)

            #ic("vstupujeme do orderupdatebuy")
            print(data)
            #dostavame zde i celkové akutální množství - ukládáme
            self.state.positions = data.position_qty
            self.state.avgp, self.state.positions = self.state.interface.pos()

        if o.status == OrderStatus.FILLED or o.status == OrderStatus.CANCELED:
            #davame pryc pending
            self.state.vars.pending = None


    async def orderUpdateSell(self, data: TradeUpdate): 

        self.state.ilog(e="Příchozí SELL notif", msg=data.order.status, trade=json.loads(json.dumps(data, default=json_serial)))

        #naklady vypocteme z prumerne ceny, kterou mame v pozicich
        if data.event == TradeEvent.FILL or data.event == TradeEvent.PARTIAL_FILL:            

           #pokud jde o fill pred kterym je partail, muze se stat, ze uz budou vynulovany pozice, toto je pojistka
           #jde o uzavření long pozice - počítáme PROFIT
            if int(self.state.positions) > 0 or (int(self.state.positions) == 0 and self.state.wait_for_fill is not None):

                if data.event == TradeEvent.PARTIAL_FILL and self.state.wait_for_fill is None:
                    #timto si oznacime, ze po partialu s vlivem na PROFIT musime cekat na FILL a zaroven ukladame prum cenu, kterou potrebujeme na vypocet profitu u fillu
                    self.state.wait_for_fill = float(self.state.avgp)

                #PROFIT pocitame z TradeUpdate.price a TradeUpdate.qty - aktualne provedene mnozstvi a cena
                #naklady vypocteme z prumerne ceny, kterou mame v pozicich
                sold_amount = data.qty * data.price
                if float(self.state.avgp) > 0:
                    vstup_cena = float(self.state.avgp)
                elif float(self.state.avgp) == 0 and self.state.wait_for_fill is not None:
                    vstup_cena = float(self.state.wait_for_fill)
                else:
                    vstup_cena = 0

                #podle prumerne ceny, kolik stalo toto mnozstvi
                avg_costs = vstup_cena * float(data.qty)
 
                if avg_costs == 0:
                    self.state.ilog(e="ERR: Nemame naklady na PROFIT, AVGP je nula. Zaznamenano jako 0", msg="naklady=utrzena cena. TBD opravit.")
                    avg_costs = sold_amount
                
                trade_profit = round((sold_amount - avg_costs),2)
                self.state.profit += trade_profit

                rel_profit = 0
                #spoctene celkovy relativni profit za trade v procentech ((trade_profit/vstup_naklady)*100)
                if vstup_cena != 0 and data.order.qty != 0:
                    rel_profit = round((trade_profit / (vstup_cena * float(data.order.qty))) * 100,5)

                rel_profit_cum_calculated = 0
                #pokud jde o finalni FILL - pridame do pole relativnich profit (ze ktereho se pocita kumulativni relativni profit)
                if data.event == TradeEvent.FILL:
                    self.state.rel_profit_cum.append(rel_profit)
                    rel_profit_cum_calculated = round(np.mean(self.state.rel_profit_cum),5)

                self.state.ilog(e=f"SELL notif - PROFIT:{round(float(trade_profit),3)} celkem:{round(float(self.state.profit),3)} rel:{float(rel_profit)} rel_cum:{round(rel_profit_cum_calculated,7)}", msg=str(data.event), rel_profit_cum = str(self.state.rel_profit_cum), sold_amount=sold_amount, avg_costs=avg_costs, trade_qty=data.qty, trade_price=data.price, orderid=str(data.order.id))

                #zapsat profit do prescr.trades
                for trade in self.state.vars.prescribedTrades:
                    if trade.id == self.state.vars.pending:
                        trade.last_update = datetime.fromtimestamp(self.state.time).astimezone(zoneNY)
                        trade.profit += trade_profit
                        #pro ulozeni do tradeData scitame vsechen zisk z tohoto tradu (kvuli partialum)
                        trade_profit = trade.profit
                        trade.profit_sum = self.state.profit
                        trade.rel_profit = rel_profit
                        trade.rel_profit_cum = rel_profit_cum_calculated
                        signal_name = trade.generated_by
                        if data.event == TradeEvent.FILL:
                            trade.status == TradeStatus.CLOSED
                        break

                if data.event == TradeEvent.FILL:
                    #mazeme self.state.
                    self.state.wait_for_fill = None
                    #zapsat update profitu do tradeList
                    for tradeData in self.state.tradeList:
                        if tradeData.execution_id == data.execution_id:
                            #pridat jako attribut, aby proslo i na LIVE a PAPPER, kde se bere TradeUpdate z Alpaca
                            setattr(tradeData, "profit", trade_profit)
                            setattr(tradeData, "profit_sum", self.state.profit)
                            setattr(tradeData, "signal_name", signal_name)
                            #self.state.ilog(f"updatnut tradeList o profi {str(tradeData)}")
                            setattr(tradeData, "rel_profit", rel_profit)
                            setattr(tradeData, "rel_profit_cum", rel_profit_cum_calculated)
                            #sem nejspis update skutecne vstupni ceny (celk.mnozstvi(order.qty) a avg_costs), to same i druhy smer

                if await self.stop_when_max_profit_loss() is False:

                    #IF REVERSAL REQUIRED - reverse position is added to prescr.Trades with same signal name
                    if data.event == TradeEvent.FILL and self.state.vars.requested_followup is not None:
                            if self.state.vars.requested_followup == Followup.REVERSE:
                                await self.add_followup(direction=TradeDirection.SHORT, size=data.order.qty, signal_name=signal_name)
                            elif self.state.vars.requested_followup == Followup.ADD:
                                #zatim stejna SIZE
                                await self.add_followup(direction=TradeDirection.LONG, size=data.order.qty, signal_name=signal_name)                            

            else:
                #zjistime nazev signalu a updatneme do tradeListu - abychom meli svazano
                for trade in self.state.vars.prescribedTrades:
                    if trade.id == self.state.vars.pending:
                        signal_name = trade.generated_by

                #zapsat update profitu do tradeList
                for tradeData in self.state.tradeList:
                    if tradeData.execution_id == data.execution_id:
                        setattr(tradeData, "signal_name", signal_name)

                self.state.ilog(e="SELL: Jde o SHORT nepocitame profit zatim")

                if data.event == TradeEvent.FILL:
                    #zapisujeme last entry price
                    self.state.last_entry_price["short"] = data.price
                    #pokud neni nastaveno goal_price tak vyplnujeme defaultem
                    if self.state.vars.activeTrade.goal_price is None:
                        dat = dict(close=data.price)
                        self.state.vars.activeTrade.goal_price = get_profit_target_price(self.state, dat, TradeDirection.SHORT)
                    #sem v budoucnu dat i update SL
                    #if self.state.vars.activeTrade.stoploss_value is None:


            #update pozic, v trade update je i pocet zbylych pozic
            old_avgp = self.state.avgp
            old_pos = self.state.positions
            self.state.positions = int(data.position_qty)
            if int(data.position_qty) == 0:
                self.state.avgp = 0

            self.state.ilog(e="SELL notifikace "+str(data.order.status), msg="update pozic", old_avgp=old_avgp, old_pos=old_pos, avgp=self.state.avgp, pos=self.state.positions, orderid=str(data.order.id))
            #self.state.avgp, self.state.positions = self.interface.pos()

        if data.event == TradeEvent.FILL or data.event == TradeEvent.CANCELED:
            print("Příchozí SELL notifikace - complete FILL nebo CANCEL", data.event)
            self.state.vars.pending = None
            a,p = self.interface.pos()
            #pri chybe api nechavame puvodni hodnoty
            if a != -1:
                self.state.avgp, self.state.positions = a,p
            else: self.state.ilog(e=f"Chyba pri dotažení self.interface.pos() {a}")
            #ic(self.state.avgp, self.state.positions)

    #this parent method is called by strategy just once before waiting for first data
    def strat_init(self):
        #ic("strat INI function")
        #lets connect method overrides
        self.state.buy = self.buy
        self.state.sell = self.sell

        self.init(self.state)

    def call_next(self, item):
        #MAIN INDICATORS
        populate_all_indicators(item, self.state)
        
        #pro přípravu dat next nevoláme
        if self.mode == Mode.PREP:
            return
        else:
            self.next(item, self.state)

    #overidden methods
    # pouziva se pri vstupu long nebo exitu short
    # osetrit uzavreni s vice nez mam
    def buy(self, size = None, repeat: bool = False):
        print("overriden buy method")
        if size is None:
            sizer = self.state.vars.chunk
        else:
            sizer = size
        #jde o uzavreni short pozice
        if int(self.state.positions) < 0 and (int(self.state.positions) + int(sizer)) > 0:
            self.state.ilog(e="buy nelze nakoupit vic nez shortuji", positions=self.state.positions, size=size)
            print("buy nelze nakoupit vic nez shortuji") 
            return -2

        if int(self.state.positions) >= self.state.vars.maxpozic:
            self.state.ilog(e="buy Maxim mnozstvi naplneno", positions=self.state.positions)
            print("max mnostvi naplneno")
            return 0

        self.state.blockbuy = 1
        self.state.vars.lastbuyindex = self.state.bars['index'][-1]
        #self.state.ilog(e="send MARKET buy to if", msg="S:"+str(size), ltp=self.state.interface.get_last_price(self.state.symbol))
        self.state.ilog(e="send MARKET buy to if", msg="S:"+str(size), ltp=self.state.bars['close'][-1])
        return self.state.interface.buy(size=sizer)

    #overidden methods
    # pouziva se pri vstupu short nebo exitu long
    def sell(self, size = None, repeat: bool = False):
        print("overriden sell method")
        if size is None:
            size = abs(int(self.state.positions))

        #jde o uzavreni long pozice
        if int(self.state.positions) > 0 and (int(self.state.positions) - int(size)) < 0:
            self.state.ilog(e="nelze prodat vic nez longuji", positions=self.state.positions, size=size)
            print("nelze prodat vic nez longuji") 
            return -2

        #pokud shortuji a mam max pozic
        if int(self.state.positions) < 0 and abs(int(self.state.positions)) >= self.state.vars.maxpozic:
            self.state.ilog(e="short - Maxim mnozstvi naplneno", positions=self.state.positions, size=size)
            print("max mnostvi naplneno")
            return 0

        #self.state.blocksell = 1
        #self.state.vars.lastbuyindex = self.state.bars['index'][-1]
        #self.state.ilog(e="send MARKET SELL to if", msg="S:"+str(size), ltp=self.state.interface.get_last_price(self.state.symbol))
        self.state.ilog(e="send MARKET SELL to if", msg="S:"+str(size), ltp=self.state.bars['close'][-1])
        return self.state.interface.sell(size=size)
from v2realbot.strategy.base import Strategy
from v2realbot.utils.utils import parse_alpaca_timestamp, ltp, AttributeDict,trunc,price2dec, zoneNY, print
from v2realbot.utils.tlog import tlog, tlog_exception
from v2realbot.enums.enums import Mode, Order, Account
from alpaca.trading.models import TradeUpdate
from alpaca.trading.enums import TradeEvent, OrderStatus
from v2realbot.indicators.indicators import ema
#from rich import print
from random import randrange
from alpaca.common.exceptions import APIError
import copy
from threading import Event


class StrategyOrderLimitVykladaci(Strategy):
    def __init__(self, name: str, symbol: str, next: callable, init: callable, account: Account, mode: Mode = Mode.PAPER, stratvars: AttributeDict = None, open_rush: int = 30, close_rush: int = 30, pe: Event = None, se: Event = None) -> None:
        super().__init__(name, symbol, next, init, account, mode, stratvars, open_rush, close_rush, pe, se)

    async def orderUpdateBuy(self, data: TradeUpdate):
        o: Order = data.order
        self.state.ilog(e="Příchozí BUY notifikace", msg="order status:"+o.status, status=o.status, orderid=str(o.id))
        if o.status == OrderStatus.FILLED or o.status == OrderStatus.CANCELED:
            
            #pokud existuje objednavka v pendingbuys - vyhodime ji
            if self.state.vars.pendingbuys.pop(str(o.id), False):
                self.state.ilog(e="Příchozí BUY notifikace - mazeme ji z pb", msg="order status:"+o.status, orderid=str(o.id), pb=self.state.vars.pendingbuys)
                print("limit buy filled or cancelled. Vyhazujeme z pendingbuys.")
                ic(self.state.vars.pendingbuys)

        if data.event == TradeEvent.FILL or data.event == TradeEvent.PARTIAL_FILL:
            ic("vstupujeme do orderupdatebuy")
            print(data)
            #dostavame zde i celkové akutální množství - ukládáme
            self.state.positions = data.position_qty
            if self.state.vars.limitka is None:
                self.state.avgp = float(data.price)
                price=price2dec(float(o.filled_avg_price)+self.state.vars.profit)
                self.state.vars.limitka = await self.interface.sell_l(price=price, size=o.filled_qty)
                #obcas live vrati "held for orders", odchytime chybu a limitku nevytvarime - spravi to dalsi notifikace nebo konzolidace
                if self.state.vars.limitka == -1:
                    self.state.ilog(e="Vytvoreni limitky neprobehlo, vracime None", msg=str(self.state.vars.limitka))
                    self.state.vars.limitka = None
                else:
                    self.state.vars.limitka_price = price
                    self.state.ilog(e="Příchozí BUY notif - vytvarime limitku",  msg="order status:"+o.status, orderid=str(o.id), limitka=str(self.state.vars.limitka), limtka_price=self.state.vars.limitka_price)
            else:
                #avgp, pos
                self.state.avgp, self.state.positions = self.state.interface.pos()
                cena = price2dec(float(self.state.avgp) + float(self.state.vars.profit))
                try:
                    puvodni = self.state.vars.limitka
                    self.state.vars.limitka = await self.interface.repl(price=cena,orderid=self.state.vars.limitka,size=int(self.state.positions))
                    #odchyceni pripadne chyby na live
                    if self.state.vars.limitka == -1:
                        self.state.ilog(e="Zmena limitky neprobehla, vracime puvodni", msg=str(self.state.vars.limitka))
                        self.state.vars.limitka = puvodni
                    else:
                        self.state.vars.limitka_price = cena
                        self.state.ilog(e="Příchozí BUY notif - menime limitku", msg="order status:"+o.status, orderid=str(o.id), limitka=str(self.state.vars.limitka), limtka_price=self.state.vars.limitka_price, puvodni_limitka=str(puvodni))
                except APIError as e:
                    self.state.ilog(e="API ERROR pri zmene limitky", msg=str(e), orderid=str(o.id), limitka=str(self.state.vars.limitka), limitka_price=self.state.vars.limitka_price, puvodni_limitka=str(puvodni))

                    #stejne parametry - stava se pri rychle obratce, nevadi
                    if e.code == 42210000: return 0,0
                    else:
                        print("Neslo nahradit profitku. Problem",str(e))
                        raise Exception(e)

    async def orderUpdateSell(self, data: TradeUpdate):

        #PROFIT
        #profit pocitame z TradeUpdate.price a TradeUpdate.qty - aktualne provedene mnozstvi a cena
        #naklady vypocteme z prumerne ceny, kterou mame v pozicich
        if data.event == TradeEvent.FILL or data.event == TradeEvent.PARTIAL_FILL:
            sold_amount = data.qty * data.price
            #podle prumerne ceny, kolik stalo toto mnozstvi
            avg_costs = self.state.avgp * data.qty
            trade_profit = (sold_amount - avg_costs)
            self.state.profit += trade_profit
            self.state.ilog(e="SELL not - PROFIT: "+str(round(trade_profit,3))+" celkem: "+str(round(self.state.profit,3)), msg=str(data.event), sold_amount=sold_amount, avg_costs=avg_costs, trade_qty=data.qty, trade_price=data.price, orderid=str(data.order.id))

        if data.event == TradeEvent.PARTIAL_FILL:
            self.state.ilog(e="SELL notifikace - Partial fill", msg="pouze update pozic", orderid=str(data.order.id))
            ic("partial fill jen udpatujeme pozice")
            #TODO tento update mozna vyhodit a pockat vzdy na plny fill - otestovat az bude cas
            self.state.avgp, self.state.positions = self.interface.pos()
        elif data.event == TradeEvent.FILL or data.event == TradeEvent.CANCELED:
            print("Příchozí SELL notifikace - complete FILL nebo CANCEL", data.event)
            #muzeme znovu nakupovat, mazeme limitku, blockbuy a pendingbuys
            #self.state.blockbuy = 0

            ic("notifikace sell mazeme limitku a update pozic")
            #updatujeme pozice
            self.state.avgp, self.state.positions = self.interface.pos()
            ic(self.state.avgp, self.state.positions)
            self.state.vars.limitka = None
            self.state.vars.limitka_price = None
            self.state.vars.lastbuyindex = -5
            self.state.vars.jevylozeno = 0
            await self.state.cancel_pending_buys()
            self.state.ilog(e="Příchozí SELL - FILL nebo CANCEL - mazeme limitku a pb", msg="order status:"+ data.order.status, orderid=str(data.order.id), pb=self.state.vars.pendingbuys)
    
    #this parent method is called by strategy just once before waiting for first data
    def strat_init(self):
        ic("strat INI function")
        #lets connect method overrides
        self.state.buy = self.buy
        self.state.buy_l = self.buy_l
        self.state.cancel_pending_buys = self.cancel_pending_buys


    #overidden methods
    def buy(self, size = None, repeat: bool = False):
        print("overriden method to size&check maximum ")
        if int(self.state.positions) >= self.state.vars.maxpozic:
            self.state.ilog(e="buy Maxim mnozstvi naplneno", curr_positions=self.state.positions)
            print("max mnostvi naplneno")
            return 0
        if size is None:
            sizer = self.state.vars.chunk
        else:
            sizer = size
        self.state.blockbuy = 1
        self.state.vars.lastbuyindex = self.state.bars['index'][-1]
        ic(self.state.blockbuy)
        ic(self.state.vars.lastbuyindex)
        return self.state.interface.buy(size=sizer)
    
    def buy_l(self, price: float = None, size = None, repeat: bool = False):
        print("entering overriden BUY")
        if int(self.state.positions) >= self.state.vars.maxpozic:
            self.state.ilog(e="buyl Maxim mnozstvi naplneno", price=price, size=size, curr_positions=self.state.positions)
            return 0
        if size is None: size=self.state.vars.chunk
        if price is None: price=price2dec((self.state.interface.get_last_price(self.symbol)))
        ic(price)
        print("odesilame LIMIT s cenou/qty", price, size)
        self.state.ilog(e="send buy to if", msg="S:"+str(size)+" P:"+str(price), price=price, size=size)
        order = self.state.interface.buy_l(price=price, size=size)
        print("ukladame pendingbuys")
        self.state.vars.pendingbuys[str(order)]=price
        self.state.blockbuy = 1
        self.state.vars.lastbuyindex = self.state.bars['index'][-1]
        ic(self.state.blockbuy)
        ic(self.state.vars.lastbuyindex)
        self.state.ilog(e="Odslano a ulozeno do pb", order=str(order), pb=self.state.vars.pendingbuys)

    async def cancel_pending_buys(self):
        print("cancel pending buys called.")
        self.state.ilog(e="Rusime pendingy", pb=self.state.vars.pendingbuys)
        ##proto v pendingbuys pridano str(), protoze UUIN nejde serializovat
        ##padalo na variable changed during iteration, pridano
        if len(self.state.vars.pendingbuys)>0:
            tmp = copy.deepcopy(self.state.vars.pendingbuys)
            for key in tmp:
                ic(key)
                #nejprve vyhodime z pendingbuys
                self.state.vars.pendingbuys.pop(key, False)
                res = self.interface.cancel(key)
                self.state.ilog(e="Pendingy zrusen pro"+str(key), orderid=str(key), res=str(res))
                print("CANCEL PENDING BUYS RETURN", res)
        self.state.vars.pendingbuys={}        
        self.state.vars.jevylozeno = 0
        print("cancel pending buys end")
        self.state.ilog(e="Dokončeno zruseni vsech pb", pb=self.state.vars.pendingbuys)

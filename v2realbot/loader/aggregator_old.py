"""
    Aggregator mdoule containing main aggregator logic for TRADES, BARS and CBAR
"""
from v2realbot.enums.enums import RecordType, StartBarAlign
from datetime import datetime, timedelta
from v2realbot.utils.utils import parse_alpaca_timestamp, ltp, Queue,is_open_hours,zoneNY
from queue import Queue
from rich import print
from v2realbot.enums.enums import Mode
import threading
from copy import deepcopy
from msgpack import unpackb
import os
from config import DATA_DIR

class TradeAggregator:  
    def __init__(self,
                 rectype: RecordType = RecordType.BAR,
                 timeframe: int = 5,
                 minsize: int = 100,
                 update_ltp: bool = False,
                 align: StartBarAlign = StartBarAlign.ROUND,
                 mintick: int = 0,
                 exthours: bool = False):
        """
        Create trade agregator. Instance accepts trades one by one and process them and returns output type
            Trade - return trade one by one (no change)
            Bar - return finished bar in given timeframe
            CBar - returns continuous bar, finished bar is marked by confirmed status
        Args:
            timeframe (number): Resolution of bar in seconds
            update_ltp (bool): Whether to update global variable with price (usually only one instance does that)
            align: Defines alignement of first bar. ROUND - according to timeframe( 5,10,15 - for 5s timeframe), RANDOM - according to timestamp of first trade
            mintick: Applies for CBAR. Minimální mezera po potvrzeni baru a aktualizaci dalsiho nepotvrzeneho (např. pro 15s, muzeme chtit prvni tick po 5s). po teto dobe realtime.
        """
        self.rectype: RecordType = rectype
        self.timeframe = timeframe
        self.minsize = minsize
        self.update_ltp = update_ltp
        self.exthours = exthours

        if mintick >= timeframe:
            print("Mintick musi byt mensi nez timeframe")
            raise Exception

        self.mintick = mintick
        #class variables = starters
        self.iterace  = 1
        self.lasttimestamp = 0
        #inicalizace pro prvni agregaci
        self.newBar = dict(high=0, low=999999, volume = 0, trades = 0, confirmed = 0, vwap = 0, close=0, index = 1, updated = 0)
        self.bar_start = 0
        self.align = align
        self.tm: datetime = None
        self.firstpass = True
        self.vwaphelper = 0
        self.returnBar = {}
        self.lastBarConfirmed = False
        #min trade size
        self.minsize = minsize
    
        #instance variable to hold last trade price
        self.last_price = 0
        self.barindex = 1

    async def ingest_trade(self, indata, symbol):
        """
        Aggregator logic for trade record
        Args:
            indata (dict): online or offline record
        """
        data = unpackb(indata)

        #last item signal
        if data == "last": return data

        #print(data)
        ##implementing fitlers - zatim natvrdo a jen tyto: size: 1, cond in [O,C,4] opening,closed a derivately priced,
        ## 22.3. - dal jsem pryc i contingency trades [' ', '7', 'V'] - nasel jsem obchod o 30c mimo
        ## dán pryč P - prior reference time + 25centu mimo, {'t': '2023-04-12T19:45:08.63257344Z', 'x': 'D', 'p': 28.68, 's': 1000, 'c': [' ', 'P'], 'i': 71693108525109, 'z': 'A'},
        ## Q - jsou v pohode, oteviraci trady, ale O jsou jejich duplikaty
        ## přidán W - average price trade, U - Extended hours - sold out of sequence
        try:
            for i in data['c']:
                if i in ('C','O','4','B','7','V','P','W','U'): return 0
        except KeyError:
            pass

        #EXPERIMENT zkusime vyhodit vsechny pod 50 #puv if int(data['s']) == 1: return 0
        #zatim nechavame - výsledek je naprosto stejný jako v tradingview
        if int(data['s']) < self.minsize: return 0
        #{'t': 1678982075.242897, 'x': 'D', 'p': 29.1333, 's': 18000, 'c': [' ', '7', 'V'], 'i': 79372107591749, 'z': 'A', 'u': 'incorrect'}
        if 'u' in data: return 0

        #pokud projde TRADE s cenou 0.33% rozdilna oproti predchozi, pak vyhazujeme v ramci cisteni dat (cca 10ticku na 30USD)
        pct_off = 0.33
        ##ic(ltp.price)
        ##ic(ltp.price[symbol])
        
        try:
            ltp.price[symbol]
        except KeyError:
            ltp.price[symbol]=data['p']


        if float(data['p']) > float(ltp.price[symbol]) + (float(data['p'])/100*pct_off) or float(data['p']) < float(ltp.price[symbol])-(float(data['p'])/100*pct_off):
            print("ZLO", data,ltp.price[symbol])
            #nechavame zlo zatim projit
            ##return 0
            # with open("cache/wrongtrades.txt", 'a') as fp:
            #     fp.write(str(data) + 'predchozi:'+str(ltp.price[symbol])+'\n')        

        #timestampy jsou v UTC
        #TIMESTAMP format is different for online and offline trade streams
        #offline trade
        #{'t': '2023-02-17T14:30:00.16111744Z', 'x': 'J', 'p': 35.14, 's': 20, 'c': [' ', 'F', 'I'], 'i': 52983525027938, 'z': 'A'}
        #websocket trade
        #{'T': 't', 'S': 'MSFT', 'i': 372, 'x': 'V', 'p': 264.58, 's': 25, 'c': ['@', 'I'], 'z': 'C', 't': Timestamp(seconds=1678973696, nanoseconds=67312449), 'r': Timestamp(seconds=1678973696, nanoseconds=72865209)}
        #parse alpaca timestamp

        # tzn. na offline mohu pouzit >>> datetime.fromisoformat(d).timestamp() 1676644200.161117
        #orizne sice nanosekundy ale to nevadi
        #print("tady", self.mode, data['t'])
        # if self.mode == Mode.BT:
        #     data['t'] = datetime.fromisoformat(str(data['t'])).timestamp()
        # else:
        data['t'] = parse_alpaca_timestamp(data['t'])

        if not is_open_hours(datetime.fromtimestamp(data['t'])) and self.exthours is False:
            #print("AGG: trade not in open hours skipping", datetime.fromtimestamp(data['t']).astimezone(zoneNY))
            return 0

        #tady bude vzdycky posledni cena a posledni cas
        if self.update_ltp:
            ltp.price[symbol] = data['p']
            ltp.time[symbol] = data['t']

        #if data['p'] < self.last_price - 0.02: print("zlo:",data)

        if self.rectype == RecordType.TRADE: return data

        #print("agr přišel trade", datetime.fromtimestamp(data['t']),data)

        #OPIC pokud bude vadit, ze prvni bar neni kompletni - pak zapnout tuto opicarnu
        #kddyz jde o prvni iteraci a pozadujeme align, cekame na kulaty cas (pro 5s 0,5,10..)
        # if self.lasttimestamp ==0 and self.align:
        #     if self.firstpass:
        #         self.tm = datetime.fromtimestamp(data['t'])
        #         self.tm += timedelta(seconds=self.timeframe)
        #         self.tm = self.tm - timedelta(seconds=self.tm.second % self.timeframe,microseconds=self.tm.microsecond)
        #         self.firstpass = False
        #     print("trade: ",datetime.fromtimestamp(data['t']))
        #     print("required",self.tm)
        #     if self.tm > datetime.fromtimestamp(data['t']):
        #         return
        #     else: pass

        #print("barstart",datetime.fromtimestamp(self.bar_start))
        #print("oriznute data z tradu", datetime.fromtimestamp(int(data['t'])))
        #print("timeframe",self.timeframe)
        if  int(data['t']) - self.bar_start < self.timeframe:
            issamebar = True
        else:
            issamebar = False
            ##flush předchozí bar a incializace (krom prvni iterace)
            if self.lasttimestamp ==0: pass
            else:
                self.newBar['confirmed'] = 1
                self.newBar['vwap'] = self.vwaphelper / self.newBar['volume']
                #updatujeme čas - obsahuje datum tradu, který confirm triggeroval
                self.newBar['updated'] = data['t']
                
                #ulozime datum akt.tradu pro mintick
                self.lastBarConfirmed = True
                #ukládám si předchozí (confirmed)bar k vrácení
                self.returnBar = self.newBar
                #print(self.returnBar)

                #inicializuji pro nový bar
                self.vwaphelper = 0

                # return self.newBar
                ##flush CONFIRMED bar to queue
                #self.q.put(self.newBar)
                ##TODO pridat prubezne odesilani pokud je pozadovano
                self.barindex +=1
                self.newBar =  {
                    "close": 0,
                    "high": 0,
                    "low": 99999999,
                    "volume": 0,
                    "trades": 0,
                    "hlcc4": 0,
                    "confirmed": 0,
                    "updated": 0,
                    "vwap": 0,
                    "index": self.barindex
                    }
            
        #je cena stejna od predchoziho tradu? pro nepotvrzeny cbar vracime jen pri zmene ceny  
        if self.last_price == data['p']:
            diff_price = False
        else:
            diff_price = True    
        self.last_price = data['p'] 

        #spočteme vwap - potřebujeme předchozí hodnoty 
        self.vwaphelper += (data['p'] * data['s'])
        self.newBar['updated'] = data['t']
        self.newBar['close'] = data['p']
        self.newBar['high'] = max(self.newBar['high'],data['p'])
        self.newBar['low'] = min(self.newBar['low'],data['p'])
        self.newBar['volume'] = self.newBar['volume'] + data['s']
        self.newBar['trades'] = self.newBar['trades'] + 1
        #pohrat si s timto round
        self.newBar['hlcc4'] = round((self.newBar['high']+self.newBar['low']+self.newBar['close']+self.newBar['close'])/4,3)

        #predchozi bar byl v jine vterine, tzn. ukladame do noveho (aktualniho) pocatecni hodnoty
        if (issamebar == False):
            #zaciname novy bar

            self.newBar['open'] = data['p']
            
            #zarovname time prvniho baru podle timeframu kam patří (např. 5, 10, 15 ...) (ROUND)
            if self.align:
                t = datetime.fromtimestamp(data['t'])
                t = t - timedelta(seconds=t.second % self.timeframe,microseconds=t.microsecond)
                self.bar_start = datetime.timestamp(t)
            #nebo pouzijeme datum tradu zaokrouhlene na vteriny (RANDOM)
            else:
                #ulozime si jeho timestamp (odtum pocitame timeframe)
                t = datetime.fromtimestamp(int(data['t']))
                #timestamp
                self.bar_start = int(data['t'])
                
            
           

            self.newBar['time'] = t 
            self.newBar['resolution'] = self.timeframe
            self.newBar['confirmed'] = 0


        #uložíme do předchozí hodnoty (poznáme tak open a close)
        self.lasttimestamp = data['t']
        self.iterace += 1
        # print(self.iterace, data)

        #je tu maly bug pro CBAR - kdy prvni trade, který potvrzuje predchozi bar
        #odesle potvrzeni predchoziho baru a nikoliv open stávajícího, ten posle až druhý trade
        #což asi nevadí


        #pokud je pripraveny, vracíme předchozí confirmed bar
        if len(self.returnBar) > 0:
            self.tmp = self.returnBar
            self.returnBar = {}
            #print(self.tmp)
            return self.tmp

        #pro cont bar posilame ihned (TBD vwap a min bar tick value)
        if self.rectype == RecordType.CBAR:

            #pokud je mintick nastavený a předchozí bar byl potvrzený
            if self.mintick != 0 and self.lastBarConfirmed:
               #d zacatku noveho baru musi ubehnout x sekund nez posilame updazte
                #pocatek noveho baru + Xs  musi byt vetsi nez aktualni trade              
                if (self.newBar['time'] + timedelta(seconds=self.mintick)) > datetime.fromtimestamp(data['t']):
                    #print("waiting for mintick")
                    return 0
                else:
                    self.lastBarConfirmed = False
            
            #doplnime prubezny vwap
            self.newBar['vwap'] = self.vwaphelper / self.newBar['volume']
            #print(self.newBar)

            #pro (nepotvrzeny) cbar vracime jen pri zmene ceny
            if diff_price is True:
                return self.newBar
            else:
                return 0
        else:
            return 0


class TradeAggregator2Queue(TradeAggregator):
    """
    Child of TradeAggregator - sends items to given queue
    In the future others will be added - TradeAggToTxT etc.
    """
    def __init__(self, symbol: str, queue: Queue, rectype: RecordType = RecordType.BAR, timeframe: int = 5, minsize: int = 100, update_ltp: bool = False, align: StartBarAlign = StartBarAlign.ROUND, mintick: int = 0, exthours: bool = False):
        super().__init__(rectype=rectype, timeframe=timeframe, minsize=minsize, update_ltp=update_ltp, align=align, mintick=mintick, exthours=exthours)
        self.queue = queue
        self.symbol = symbol

    async def ingest_trade(self, data):
            #print("ingest ve threadu:",current_thread().name)
            res = await super().ingest_trade(data, self.symbol)
            if res != 0:
                #print(res)
                #pri rychlem plneni vetsiho dictionary se prepisovali - vyreseno kopií
                if isinstance(res, dict):
                    copy = res.copy()
                else:
                    copy = res
                self.queue.put(copy)
            res = {}
            #print("po insertu",res)

class TradeAggregator2List(TradeAggregator):
    """"
    stores records to the list
    """
    def __init__(self, symbol: str, btdata: list, rectype: RecordType = RecordType.BAR, timeframe: int = 5, minsize: int = 100, update_ltp: bool = False, align: StartBarAlign = StartBarAlign.ROUND, mintick: int = 0, exthours: bool = False):
        super().__init__(rectype=rectype, timeframe=timeframe, minsize=minsize, update_ltp=update_ltp, align=align, mintick=mintick, exthours=exthours)
        self.btdata = btdata
        self.symbol = symbol
        # self.debugfile = DATA_DIR + "/BACprices.txt"
        # if os.path.exists(self.debugfile):
        #     os.remove(self.debugfile)

    async def ingest_trade(self, data):
            #print("ted vstoupil do tradeagg2list ingestu")
            res1 = await super().ingest_trade(data, self.symbol)
            #print("ted je po zpracovani", res1)
            if res1 != 0:
                #pri rychlem plneni vetsiho dictionary se prepisovali - vyreseno kopií
                if isinstance(res1, dict):
                    copy = res1.copy()
                else:
                    copy = res1
                if res1 == 'last': return 0
                self.btdata.append((copy['t'],copy['p']))
                # with open(self.debugfile, "a") as output:
                #     output.write(str(copy['t']) + ' ' + str(datetime.fromtimestamp(copy['t']).astimezone(zoneNY)) + ' ' + str(copy['p']) + '\n')
            res1 = {}
                #print("po insertu",res)




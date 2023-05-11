import os,sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from v2realbot.strategy.base import StrategyState
from v2realbot.strategy.StrategyOrderLimitVykladaci import StrategyOrderLimitVykladaci
from v2realbot.enums.enums import RecordType, StartBarAlign, Mode, Account, OrderSide, OrderType
from v2realbot.indicators.indicators import ema
from v2realbot.indicators.oscillators import rsi, stochastic_oscillator, stochastic_rsi, absolute_price_oscillator, percentage_price_oscillator
from v2realbot.utils.utils import ltp, isrising, isfalling,trunc,AttributeDict, zoneNY, price2dec, print, safe_get
from datetime import datetime
#from icecream import install, ic
#from rich import print
from threading import Event
from msgpack import packb, unpackb
import asyncio
import os
from traceback import format_exc

def next(data, state: StrategyState):
    print(10*"*","NEXT START",10*"*")
    #ic(state.avgp, state.positions)
    #ic(state.vars)
    #ic(data)

    #
    def is_defensive_mode():
        akt_pozic = int(state.positions)
        max_pozic = int(state.vars.maxpozic)
        def_mode_from = safe_get(state.vars, "def_mode_from")
        if def_mode_from == None: def_mode_from = max_pozic/2
        if akt_pozic >= int(def_mode_from):
            state.ilog(e=f"DEFENSIVE mode ACTIVE {state.vars.def_mode_from=}", msg=state.positions)
            return True
        else:
            state.ilog(e=f"STANDARD mode ACTIVE {state.vars.def_mode_from=}", msg=state.positions)
            return False

    def get_limitka_price():
        def_profit = safe_get(state.vars, "def_profit") 
        if def_profit == None: def_profit = state.vars.profit
        if is_defensive_mode():
            return price2dec(float(state.avgp)+float(def_profit))
        else:
            return price2dec(float(state.avgp)+float(state.vars.profit))
 
    def consolidation():
        ##CONSOLIDATION PART - moved here, musí být před nákupem, jinak to dělalo nepořádek v pendingbuys
        #docasne zkusime konzolidovat i kdyz neni vylozeno (aby se srovnala limitka ve vsech situacich)
        if state.vars.jevylozeno == 1 or 1==1:
            ##CONSOLIDATION PART kazdy Nty bar dle nastaveni
            if int(data["index"])%int(state.vars.consolidation_bar_count) == 0:
                print("***CONSOLIDATION ENTRY***")
                state.ilog(e="CONSOLIDATION ENTRY ***")

                orderlist = state.interface.get_open_orders(symbol=state.symbol, side=None)
                #pro jistotu jeste dotahneme aktualni pozice
                state.avgp, state.positions = state.interface.pos()            

                #print(orderlist)
                pendingbuys_new = {}
                limitka_old = state.vars.limitka
                #print("Puvodni LIMITKA", limitka_old)
                #zaciname s cistym stitem
                state.vars.limitka = None
                state.vars.limitka_price = None
                limitka_found = False
                limitka_qty = 0
                limitka_filled_qty = 0
                for o in orderlist:
                    if o.side == OrderSide.SELL:
                        
                        if limitka_found:
                            state.ilog(e="nalezeno vicero sell objednavek, bereme prvni, ostatni - rusime")
                            result=state.interface.cancel(o.id)
                            state.ilog(e="zrusena objednavka"+str(o.id), message=result)
                            continue
                        
                        #print("Nalezena LIMITKA")
                        limitka_found = True
                        state.vars.limitka = o.id
                        state.vars.limitka_price = o.limit_price
                        limitka_qty = int(o.qty)
                        limitka_filled_qty = int(o.filled_qty)

                        #aktualni mnozstvi = puvodni minus filled
                        if limitka_filled_qty is not None:
                            print("prepocitavam filledmnozstvi od limitka_qty a filled_qty", limitka_qty, limitka_filled_qty)
                            limitka_qty = int(limitka_qty) - int(limitka_filled_qty)
                        ##TODO sem pridat upravu ceny
                    if o.side == OrderSide.BUY and o.order_type == OrderType.LIMIT:
                        pendingbuys_new[str(o.id)]=float(o.limit_price)

                state.ilog(e="Konzolidace limitky", msg=f"stejna:{(str(limitka_old)==str(state.vars.limitka))}", limitka_old=str(limitka_old), limitka_new=str(state.vars.limitka), limitka_new_price=state.vars.limitka_price, limitka_qty=limitka_qty, limitka_filled_qty=limitka_filled_qty)
                
                #pokud mame 

                #neni limitka, ale mela by byt - vytváříme ji
                if int(state.positions) > 0 and state.vars.limitka is None:
                    state.ilog(e="Limitka neni, ale mela by být.", msg=f"{state.positions=}")
                    price=get_limitka_price()
                    state.vars.limitka = asyncio.run(state.interface.sell_l(price=price, size=int(state.positions)))
                    state.vars.limitka_price = price
                    if state.vars.limitka == -1:
                        state.ilog(e="Vytvoreni limitky neprobehlo, vracime None", msg=f"{state.vars.limitka=}")
                        state.vars.limitka = None
                        state.vars.limitka_price = None
                    else:
                        state.ilog(e="Vytvořena nová limitka", limitka=str(state.vars.limitka), limtka_price=state.vars.limitka_price, qty=state.positions)

                #existuje a nesedi mnozstvi nebo cena
                elif state.vars.limitka is not None and int(state.positions) > 0 and ((int(state.positions) != int(limitka_qty)) or float(state.vars.limitka_price) != float(get_limitka_price())):
                    #limitka existuje, ale spatne mnostvi - updatujeme
                    state.ilog(e=f"Limitka existuje, ale spatne mnozstvi nebo CENA - updatujeme", msg=f"{state.positions=} {limitka_qty=} {state.vars.limitka_price=}", nastavenacena=state.vars.limitka_price, spravna_cena=get_limitka_price(), pos=state.positions, limitka_qty=limitka_qty)
                    #snad to nespadne, kdyztak pridat exception handling
                    puvodni = state.vars.limitka
                    #TBD zde odchytit nejak result
                    state.vars.limitka = asyncio.run(state.interface.repl(price=get_limitka_price(), orderid=state.vars.limitka, size=int(state.positions)))
                    
                    if state.vars.limitka == -1:
                        state.ilog(e="Replace limitky neprobehl, vracime puvodni", msg=f"{state.vars.limitka=}", puvodni=puvodni)
                        state.vars.limitka = puvodni
                    else:   
                        limitka_qty = int(state.positions)
                        state.ilog(e="Změněna limitka", limitka=str(state.vars.limitka), limitka_price=state.vars.limitka_price, limitka_qty=limitka_qty)

                #tbd pokud se bude vyskytovat pak pridat ještě konzolidaci ceny limitky

                if pendingbuys_new != state.vars.pendingbuys:
                    state.ilog(e="Rozdilna PB prepsana", pb_new=pendingbuys_new, pb_old = state.vars.pendingbuys)
                    print("ROZDILNA PENDINGBUYS přepsána")
                    print("OLD",state.vars.pendingbuys)
                    state.vars.pendingbuys = unpackb(packb(pendingbuys_new))
                    print("NEW", state.vars.pendingbuys)
                else:
                    print("PENDINGBUYS sedí - necháváme", state.vars.pendingbuys)
                    state.ilog(e="PB sedi nechavame", pb_new=pendingbuys_new, pb_old = state.vars.pendingbuys)
                print("OLD jevylozeno", state.vars.jevylozeno)
                if len(state.vars.pendingbuys) > 0:
                    state.vars.jevylozeno = 1
                else:
                    state.vars.jevylozeno = 0
                print("NEW jevylozeno", state.vars.jevylozeno)
                state.ilog(e="Nove jevylozeno", msg=state.vars.jevylozeno)

                #print(limitka)
                #print(pendingbuys_new)
                #print(pendingbuys)
                #print(len(pendingbuys))
                #print(len(pendingbuys_new))
                #print(jevylozeno)
                print("***CONSOLIDATION EXIT***")
                state.ilog(e="CONSOLIDATION EXIT ***")
            else:
                state.ilog(e="No time for consolidation", msg=data["index"])
                print("no time for consolidation", data["index"])

    #mozna presunout o level vys
    def vyloz():
        ##prvni se vyklada na aktualni cenu, další jdou podle krivky, nula v krivce zvyšuje množství pro následující iteraci
        #curve = [0.01, 0.01, 0, 0, 0.01, 0, 0, 0, 0.02, 0, 0, 0, 0.03, 0,0,0,0,0, 0.02, 0,0,0,0,0,0, 0.02]
        curve = state.vars.curve
        ##defenzivni krivka pro 
        curve_def = state.vars.curve_def
        #vykladani po 5ti kusech, když zbývají 2 a méně, tak děláme nový výklad
        vykladka = state.vars.vykladka
        #kolik muzu max vylozit
        kolikmuzu = int((int(state.vars.maxpozic) - int(state.positions))/int(state.vars.chunk))
        akt_pozic = int(state.positions)
        max_pozic = int(state.vars.maxpozic)

        #mame polovinu a vic vylozeno, pouzivame defenzicni krivku
        if is_defensive_mode():
            state.ilog(e="DEF: Pouzivame defenzivni krivku", akt_pozic=akt_pozic, max_pozic=max_pozic, curve_def=curve_def)
            curve = curve_def
            #zaroven docasne menime ticks2reset na defenzivni 0.06
            state.vars.ticks2reset = 0.06
            state.ilog(e="DEF: Menime tick2reset na 0.06", ticks2reset=state.vars.ticks2reset, ticks2reset_backup=state.vars.ticks2reset_backup)
        else:
            #vracime zpet, pokud bylo zmeneno
            if state.vars.ticks2reset != state.vars.ticks2reset_backup:
                state.vars.ticks2reset = state.vars.ticks2reset_backup
                state.ilog(e="DEF: Menime tick2reset zpet na"+str(state.vars.ticks2reset), ticks2reset=state.vars.ticks2reset, ticks2reset_backup=state.vars.ticks2reset_backup)

        if kolikmuzu < vykladka: vykladka = kolikmuzu

        if len(curve) < vykladka:
            vykladka = len(curve)
        qty = int(state.vars.chunk)
        last_price = price2dec(state.interface.get_last_price(state.symbol))
        #profit = float(state.vars.profit)
        price = last_price
        state.ilog(e="BUY Vykladame", msg=f"first price {price=} {vykladka=}", curve=curve, ema=state.indicators.ema[-1], trend=state.vars.Trend, price=price, vykladka=vykladka)
        ##prvni se vyklada na aktualni cenu, další jdou podle krivky, nula v krivce zvyšuje množství pro následující iteraci
        
        ##VAR - na zaklade conf. muzeme jako prvni posilat MARKET order
        if safe_get(state.vars, "first_buy_market") == True:
            #pri defenzivnim rezimu pouzivame vzdy LIMIT order
            if is_defensive_mode():
                state.ilog(e="DEF mode on, odesilame jako prvni limitku")
                state.buy_l(price=price, size=qty)
            else:
                state.ilog(e="Posilame jako prvni MARKET order")
                state.buy(size=qty)
        else:
            state.buy_l(price=price, size=qty)
        print("prvni limitka na aktuální cenu. Další podle křivky", price, qty)
        for i in range(0,vykladka-1):
            price = price2dec(float(price - curve[i]))
            if price == last_price:
                qty = qty + int(state.vars.chunk)
            else:
                state.buy_l(price=price, size=qty)
                #print(i,"BUY limitka - delta",curve[i]," cena:", price, "mnozstvi:", qty)
                qty = int(state.vars.chunk)
            last_price = price
        state.vars.blockbuy = 1
        state.vars.jevylozeno = 1

    #CBAR protection,  only 1x order per CBAR - then wait until another confirmed bar
    if state.vars.blockbuy == 1 and state.rectype == RecordType.CBAR:
        if state.bars.confirmed[-1] == 0:
            print("OCHR: multibuy protection. waiting for next bar")
            return 0
        # pop potvrzeni jeste jednou vratime (aby se nekoupilo znova, je stale ten stejny bar)
        # a pak dalsi vejde az po minticku
        else:
            # pro vykladaci
            state.vars.blockbuy = 0
            return 0

    state.ilog(e="-----")

    #EMA INDICATOR - 
    #plnime MAcko - nyni posilame jen N poslednich hodnot
    #zaroven osetrujeme pripady, kdy je malo dat a ukladame nulu
    try:
        ma = int(state.vars.MA)
        #poslednich ma hodnot
        source = state.bars.close[-ma:] #state.bars.vwap
        ema_value = ema(source, ma)
        state.indicators.ema.append(trunc(ema_value[-1],3))
    except Exception as e:
        state.ilog(e="EMA ukladame 0", message=str(e)+format_exc())
        state.indicators.ema.append(0)

    #EMA SLOW 
    try:
        ma = 100
        #poslednich ma hodnot
        source = state.bars.hlcc4[-ma:] #state.bars.vwap
        emaSlow_value = ema(source, ma)
        emaSlow = trunc(emaSlow_value[-1],3)
        state.indicators.emaSlow.append(emaSlow)
        state.ilog(e=f"emaSlow {emaSlow=}", emaSlow=state.indicators.emaSlow[-5:])
    except Exception as e:
        state.ilog(e=f"emaSlow {ma=} ukladame 0", message=str(e)+format_exc())
        state.indicators.emaSlow.append(0)


    #EMA FAST
    try:
        ma = 20
        #poslednich ma hodnot
        source = state.bars.hlcc4[-ma:] #state.bars.vwap
        emaFast_value = ema(source, ma)
        emaFast = trunc(emaFast_value[-1],3)
        state.indicators.emaFast.append(emaFast)
        state.ilog(e=f"emaFast {emaFast=}", emaFast=state.indicators.emaFast[-5:])
    except Exception as e:
        state.ilog(e=f"emaFast {ma=} ukladame 0", message=str(e)+format_exc())
        state.indicators.emaFast.append(0)


    #RSI14
    try:
        rsi_length = 14
        #poslednich ma hodnot
        source = state.bars.close #[-rsi_length:] #state.bars.vwap
        rsi_res = rsi(source, rsi_length)
        rsi_value = trunc(rsi_res[-1],3)
        state.indicators.RSI14.append(rsi_value)
        state.ilog(e=f"RSI {rsi_length=} {rsi_value=}", rsi_indicator=state.indicators.RSI14[-5:])
    except Exception as e:
        state.ilog(e=f"RSI {rsi_length=} ukladame 0", message=str(e)+format_exc())
        state.indicators.RSI14.append(0)

    #stoch
    try:
        stoch_length = 14
        #poslednich ma hodnot
        source_high = state.bars.high #[-rsi_length:] #state.bars.vwap
        source_low = state.bars.low
        source_close=state.bars.close
        stoch_res1, stoch_res2 = stochastic_oscillator(source_high, source_low, source_close)
        stoch_value1 = trunc(stoch_res1[-1],3)
        stoch_value2 = trunc(stoch_res2[-1],3)
        state.indicators.stoch1.append(stoch_value1)
        state.indicators.stoch2.append(stoch_value2)
        state.ilog(e=f"stoch {stoch_value1=} {stoch_value2=}", stoch1=state.indicators.stoch1[-5:], stoch2=state.indicators.stoch2[-5:])
    except Exception as e:
        state.ilog(e=f"stoch ukladame 0", message=str(e)+format_exc())
        state.indicators.stoch1.append(0)
        state.indicators.stoch2.append(0)


    #absolute price oscillator
    #meri mezeru mezi dvemi MACky (ato bud absolut price nebo percentage)
    try:
        short = 1
        long = 20
        #poslednich ma hodnot
        source = state.bars.close #[-rsi_length:] #state.bars.vwap
        apo_res = absolute_price_oscillator(source, short,long)
        apo_value = trunc(apo_res[-1],3)
        state.indicators.apo.append(apo_value)
        state.ilog(e=f"apo {apo_value=}", apo_indicator=state.indicators.apo[-5:])
    except Exception as e:
        state.ilog(e=f"apo ukladame 0", message=str(e)+format_exc())
        state.indicators.apo.append(0)

   #percentage price oscillator
    try:
        short = 1
        long = 20
        #poslednich ma hodnot
        source = state.bars.close #[-rsi_length:] #state.bars.vwap
        ppo_res = percentage_price_oscillator(source, short,long)
        ppo_value = trunc(ppo_res[-1],3)
        state.indicators.ppo.append(ppo_value)
        state.ilog(e=f"poo {ppo_value=}", ppo_indicator=state.indicators.ppo[-5:])
    except Exception as e:
        state.ilog(e=f"ppo ukladame 0", message=str(e)+format_exc())
        state.indicators.ppo.append(0)


    #SLOPE INDICATOR
    #úhel stoupání a klesání vyjádřený mezi -1 až 1
    #pravý bod přímky je aktuální cena, levý je průměr X(lookback offset) starších hodnot od slope_lookback.
    #obsahuje statický indikátor (angle) pro vizualizaci
    try:
        slope = 99
        slope_lookback = int(state.vars.slope_lookback)
        minimum_slope = float(state.vars.minimum_slope)
        lookback_offset = int(state.vars.lookback_offset)

        if len(state.bars.close) > (slope_lookback + lookback_offset):
            array_od = slope_lookback + lookback_offset
            array_do = slope_lookback
            lookbackprice_array = state.bars.vwap[-array_od:-array_do]
            #obycejný prumer hodnot
            lookbackprice = round(sum(lookbackprice_array)/lookback_offset,3)

            #výpočet úhlu
            slope = ((state.bars.close[-1] - lookbackprice)/lookbackprice)*100
            slope = round(slope, 4)
            state.indicators.slope.append(slope)
 
            #angle je ze slope
            state.statinds.angle = dict(time=state.bars.time[-1], price=state.bars.close[-1], lookbacktime=state.bars.time[-slope_lookback], lookbackprice=lookbackprice, minimum_slope=minimum_slope)
 
            #slope MA vyrovna vykyvy ve slope, dále pracujeme se slopeMA
            slope_MA_length = 5
            source = state.indicators.slope[-slope_MA_length:]
            slopeMAseries = ema(source, slope_MA_length) #state.bars.vwap
            slopeMA = slopeMAseries[-1]
            state.indicators.slopeMA.append(slopeMA)

            state.ilog(e=f"{slope=} {slopeMA=}", msg=f"{lookbackprice=}", lookbackoffset=lookback_offset, minimum_slope=minimum_slope, last_slopes=state.indicators.slope[-10:])

            #dale pracujeme s timto MAckovanym slope
            slope = slopeMA         
        else:
            #pokud plnime historii musime ji plnit od zacatku, vsehcny idenitifkatory maji spolecny time
            #kvuli spravnemu zobrazovani na gui
            state.indicators.slope.append(0)
            state.indicators.slopeMA.append(0)
            state.ilog(e="Slope - not enough data", slope_lookback=slope_lookback, slope=state.indicators.slope, slopeMA=state.indicators.slopeMA)
    except Exception as e:
        print("Exception in NEXT Slope Indicator section", str(e))
        state.ilog(e="EXCEPTION", msg="Exception in Slope Indicator section" + str(e) + format_exc())

    print("is falling",isfalling(state.indicators.ema,state.vars.Trend))
    print("is rising",isrising(state.indicators.ema,state.vars.Trend))

    consolidation()

    #HLAVNI ITERACNI LOG JESTE PRED AKCI - obsahuje aktualni hodnoty vetsiny parametru
    lp = state.interface.get_last_price(symbol=state.symbol)
    state.ilog(e="ENTRY", msg=f"LP:{lp} P:{state.positions}/{round(float(state.avgp),3)} profit:{round(float(state.profit),2)} Trades:{len(state.tradeList)} DEF:{str(is_defensive_mode())}", last_price=lp, data=data, stratvars=state.vars)

    #SLOPE ANGLE PROTECTIONs
    #slope zachycuje rychle sestupy, pripadne zrusi nakupni objednavky
    if slope < minimum_slope: # or slopeMA<maxSlopeMA:
        print("OCHRANA SLOPE TOO HIGH")
        # if slopeMA<maxSlopeMA:
        #     state.ilog(e="Slope MA too high "+str(slopeMA)+" max:"+str(maxSlopeMA))
        state.ilog(e=f"Slope too high {slope}")
        if len(state.vars.pendingbuys)>0:
            print("CANCEL PENDINGBUYS")
            #ic(state.vars.pendingbuys)
            res = asyncio.run(state.cancel_pending_buys())
            #ic(state.vars.pendingbuys)
            state.ilog(e="Rusime pendingbuyes", pb=state.vars.pendingbuys, res=res)
        print("slope", slope)
        print("min slope", minimum_slope)

    if state.vars.jevylozeno == 0:
        print("Neni vylozeno, muzeme testovat nakup")

        #pokud je defenziva, buy triggeruje defenzivni def_trend
        #TBD


        if isfalling(state.indicators.ema,state.vars.Trend) and slope > minimum_slope:
            vyloz()

    if state.vars.jevylozeno == 1:
        #pokud mame vylozeno a cena je vetsi nez tick2reset 
            if len(state.vars.pendingbuys)>0:
                maxprice = max(state.vars.pendingbuys.values())
                print("max cena v orderbuys", maxprice)
                if state.interface.get_last_price(state.symbol) > float(maxprice) + float(state.vars.ticks2reset):
                    ##TODO toto nejak vymyslet - duplikovat?
                    res = asyncio.run(state.cancel_pending_buys())
                    state.ilog(e=f"UJELO to. Rusime PB", msg=f"{state.vars.ticks2reset=}", pb=state.vars.pendingbuys)

            #PENDING BUYS SPENT - PART
            #pokud mame vylozeno a pendingbuys se vyklepou a 
            # 1 vykladame idned znovu
                # vyloz()
            # 2 nebo - počkat zase na signál a pokračovat dál  
                # state.vars.blockbuy = 0
                # state.vars.jevylozeno = 0
            # 3 nebo - počkat na signál s enablovaným lastbuy indexem (tzn. počká nutně ještě pár barů)   
            #podle BT vyhodnejsi vylozit ihned
            if len(state.vars.pendingbuys) == 0:
                state.vars.blockbuy = 0
                state.vars.jevylozeno = 0
                state.ilog(e="PB se vyklepaly nastavujeme: neni vylozeno", jevylozeno=state.vars.jevylozeno)

            #TODO toto dodelat konzolidaci a mozna lock na limitku a pendingbuys a jevylozeno ??

            #kdykoliv se muze notifikace ztratit 
                # - pendingbuys - vsechny open orders buy
                # - limitka - open order sell




            

            #pokud je vylozeno a mame pozice a neexistuje limitka - pak ji vytvorim
            # if int(state.oe.poz)>0 and state.oe.limitka == 0:
            #     #pro jistotu updatujeme pozice
            #     state.oe.avgp, state.oe.poz = state.oe.pos()
            #     if int(state.oe.poz) > 0:
            #         cena = round(float(state.oe.avgp) + float(state.oe.stratvars["profit"]),2)
            #         print("BUGF: limitka neni vytvarime, a to za cenu",cena,"mnozstvi",state.oe.poz)
            #         print("aktuzalni ltp",ltp.price[state.oe.symbol])

            #         try:
            #             state.oe.limitka = state.oe.sell_noasync(cena, state.oe.poz)
            #             print("vytvorena limitka", state.oe.limitka)
            #         except Exception as e:
            #             print("Neslo vytvorit profitku. Problem,ale jedeme dal",str(e))
            #             pass
            #             ##raise Exception(e)

    print(10*"*","NEXT STOP",10*"*")

def init(state: StrategyState):
    #place to declare new vars
    print("INIT v main",state.name)
    state.indicators['ema'] = []
    state.indicators['slope'] = []
    state.indicators['slopeMA'] = []
    state.indicators['emaSlow'] = []
    state.indicators['emaFast'] = []
    state.indicators['RSI14'] = []
    state.indicators['stoch1'] = []
    state.indicators['stoch2'] = []
    state.indicators['apo'] = []
    state.indicators['ppo'] = []
    #static indicators - those not series based
    state.statinds['angle'] = dict(minimum_slope=state.vars["minimum_slope"])
    state.vars["ticks2reset_backup"] = state.vars.ticks2reset

 
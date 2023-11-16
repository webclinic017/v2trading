from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest, StockTradesRequest, StockSnapshotRequest
from alpaca.data import Quote, Trade, Snapshot, Bar
from alpaca.data.models import BarSet, QuoteSet, TradeSet
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from v2realbot.utils.utils import zoneNY
from v2realbot.config import ACCOUNT1_PAPER_API_KEY, ACCOUNT1_PAPER_SECRET_KEY
from alpaca.data.enums import DataFeed
from datetime import datetime, timedelta
import pandas as pd
from rich import print
from collections import defaultdict
from pandas import to_datetime
from msgpack.ext import Timestamp

def convert_daily_bars(daily_bars):
  """Converts a list of daily bars into a dictionary with the specified keys.

  Args:
    daily_bars: A list of daily bars, where each bar is a dictionary with the
      following keys:
        * c: Close price
        * h: High price
        * l: Low price
        * n: Number of trades
        * o: Open price
        * t: Time in UTC (ISO 8601 format)
        * v: Volume
        * vw: VWAP

  Returns:
    A dictionary with the following keys:
      * high: A list of high prices
      * low: A list of low prices
      * volume: A list of volumes
      * close: A list of close prices
      * hlcc4: A list of HLCC4 indicators
      * open: A list of open prices
      * time: A list of times in UTC (ISO 8601 format)
      * trades: A list of number of trades
      * resolution: A list of resolutions (all set to 'D')
      * confirmed: A list of booleans (all set to True)
      * vwap: A list of VWAP indicator
      * updated: A list of booleans (all set to True)
      * index: A list of integers (from 0 to the length of the list of daily bars)
  """

  bars = defaultdict(list)
  for i in range(len(daily_bars)):
    bar = daily_bars[i]

    # Calculate the HLCC4 indicator
    hlcc4 = (bar['h'] + bar['l'] + bar['c'] + bar['o']) / 4
    datum = to_datetime(bar['t'], utc=True)

    #nebo pripadna homogenizace s online streamem
    #datum = Timestamp.from_unix(datum.timestamp())

    # Add the bar to the dictionary
    bars['high'].append(bar['h'])
    bars['low'].append(bar['l'])
    bars['volume'].append(bar['v'])
    bars['close'].append(bar['c'])
    bars['hlcc4'].append(hlcc4)
    bars['open'].append(bar['o'])
    bars['time'].append(datum)
    bars['trades'].append(bar['n'])
    bars['resolution'].append('D')
    bars['confirmed'].append(1)
    bars['vwap'].append(bar['vw'])
    bars['updated'].append(datum)
    bars['index'].append(i)

  return bars

def get_last_close():
   pass

def get_todays_open():
    pass

##vrati historicke bary v nasem formatu
def get_historical_bars(symbol: str, time_from: datetime, time_to: datetime, timeframe: TimeFrame):
    stock_client = StockHistoricalDataClient(ACCOUNT1_PAPER_API_KEY, ACCOUNT1_PAPER_SECRET_KEY, raw_data=True)
    # snapshotRequest = StockSnapshotRequest(symbol_or_symbols=[symbol], feed=DataFeed.SIP)
    # snapshotResponse = stock_client.get_stock_snapshot(snapshotRequest)
    # print("snapshot", snapshotResponse)

    bar_request = StockBarsRequest(symbol_or_symbols=symbol,timeframe=timeframe, start=time_from, end=time_to, feed=DataFeed.SIP)
    bars: BarSet = stock_client.get_stock_bars(bar_request)
    #print("puvodni bars", bars["BAC"])
    return convert_daily_bars(bars[symbol])
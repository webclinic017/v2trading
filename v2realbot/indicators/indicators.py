import tulipy as ti
import numpy as np
import pandas as pd
from collections import deque
import typing

def ema(data, period: int = 50, use_series=False):
    if check_series(data):
        use_series = True
    data = convert_to_numpy(data)
    ema = ti.ema(data, period=period)
    return pd.Series(ema) if use_series else ema

def sma(data, period: int = 50, use_series=False):
    """
    Finding the moving average of a dataset
    Args:
        data: (list) A list containing the data you want to find the moving average of
        period: (int) How far each average set should be
    """
    if check_series(data):
        use_series = True
    data = convert_to_numpy(data)
    sma = ti.sma(data, period=period)
    return pd.Series(sma) if use_series else sma

def convert_to_numpy(data):
    if isinstance(data, list) or isinstance(data, deque):
        return np.fromiter(data, float)
    elif isinstance(data, pd.Series):
        return data.to_numpy()
    return data


def check_series(data):
    return isinstance(data, pd.Series)
from math import log, sqrt, exp
import datetime as dt  # date objects
import numpy as np  # array manipulation
import matplotlib.pyplot as plot  # plotting
import pandas as pd  # data analysis
import pandas_datareader as pdr
from scipy.stats import norm

from ib_insync import *


def d1(S, K, T, r, sigma):
    return (log(S / K) + (r + sigma**2 / 2.0) * T) / (sigma * sqrt(T))


def d2(S, K, T, r, sigma):
    return d1(S, K, T, r, sigma) - sigma * sqrt(T)


def bs_call(S, K, T, r, sigma):
    return S * norm.cdf(d1(S, K, T, r, sigma)) - K * exp(-r * T) * norm.cdf(
        d2(S, K, T, r, sigma)
    )


def bs_put(S, K, T, r, sigma):
    return K * exp(-r * T) - S * bs_call(S, K, T, r, sigma)


class SpxOptions:
    def __init__(self):
        """Initialize IB connection and create a contract for the underlying"""
        # ibkr connection
        self.ib = IB()
        self.ib.connect("127.0.0.1", 4002, clientId=1)

        # price the underlying security
        spx = Index("SPX", "CBOE")
        self.ib.qualifyContracts(spx)
        self.ib.reqMarketDataType(4)
        [ticker] = self.ib.reqTickers(spx)
        self.spx_price = ticker.marketPrice()

    def get_option_chain(self):
        """Generate the option chain generator"""
        opt_chain = self.ib.reqSecDefOptParams(
            self.spx.symbol, "", self.spx.secType, self.spx.conId
        )
        chain = next(
            c for c in opt_chain if c.tradingClass == "SPX" and c.exchange == "SMART"
        )
        return chain

    def bs_price():
        """Price an option with the black-scholes model"""
        pass

    def delta_hedge(self):
        """Initiate a delta hedge for call options"""
        pass

    def rebalance(self):
        """Rebalance portfolio to remain delta-neutral
        Runs twice daily
        """
        pass


if __name__ == "__main__":
    s = SpxOptions()
    print(s)

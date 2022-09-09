"""Delta Hedging module

This module executes delta hedging code for trading assignment 1
"""

__version__ = "0.1"
__author__ = "Alistair Russell"

from math import log, sqrt, exp
import datetime as dt  # date objects
import numpy as np  # array manipulation
import matplotlib.pyplot as plot  # plotting
import pandas as pd  # data analysis
import pandas_datareader as pdr  # datareader
from scipy.stats import norm  # normal cdf

from ib_insync import *


class SpxOptions:
    """Class for pricing and hedging of SPX options

    Returns:
        obj: object with ib connection established and spx priced
    """

    def __init__(self, url="127.0.0.1", port=4002):
        """Initialize IB connection and create a contract for the underlying

        Args:
            url (str, optional): URL string for TWS or IB gateway. Defaults to "127.0.0.1".
            port (int, optional): Port number. Defaults to 4002.
        """
        # ibkr connection
        self.ib = IB()
        self.ib.connect(url, port, clientId=1)

        # price the underlying security
        spx = Index("SPX", "CBOE")
        self.ib.qualifyContracts(spx)
        self.ib.reqMarketDataType(4)
        [ticker] = self.ib.reqTickers(spx)
        self.spx_price = ticker.marketPrice()

    def _get_option_chain(self):
        """Create the option chain generator"""
        opt_chain = self.ib.reqSecDefOptParams(
            self.spx.symbol, "", self.spx.secType, self.spx.conId
        )
        chain = next(
            c for c in opt_chain if c.tradingClass == "SPX" and c.exchange == "SMART"
        )
        return chain

    def _bs_price(S, K, T, r, sigma):
        """Price an option with the black-scholes model

        Args:
            S (float): Price of the underlying security
            K (float): Strike price
            T (float): time to maturity
            r (float): risk free interest rate
            sigma (float): volatility of the underlying security

        Returns:
            float: the black-scholes price of the call option
        """
        d1 = (log(S / K) + (r + sigma**2 / 2.0) * T) / (sigma * sqrt(T))
        d2 = (S, K, T, r, sigma) - sigma * sqrt(T)
        bs_call = S * norm.cdf(d1) - K * exp(-r * T) * norm.cdf(d2)
        return bs_call

    def _delta_hedge(self):
        """Initiate a delta hedge for call options"""
        # calculate the option delta, either wait for the ibkr delta or use vollib

        # use the delta to determine the amount of stock needed to hedge

        # calculate the difference between the hedge requirement and the current portfolio

        # return trade required
        pass

    def sell_mispricing(self, num_contracts):
        """Sell contracts of the option with the largest mispricing

        Args:
            num_contracts (int): the number of contracts to sell
        """
        pass

    def rebalance(self):
        """Rebalance portfolio to remain delta-neutral
        Runs twice daily
        """
        # price the option with Black-Scholes

        # calculate the delta hedge trade needed to rebalance

        # check whether the risk outweighs the transaction cost

        # execute the trade to remain delta-neutral
        pass


if __name__ == "__main__":
    s = SpxOptions()
    s.rebalance()
    print(s)

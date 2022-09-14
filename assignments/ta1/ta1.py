"""Delta Hedging module

This module executes delta hedging code for trading assignment 1
"""

__version__ = "0.1"
__author__ = "Alistair Russell"

import datetime as dt  # date objects
import numpy as np  # array manipulation
import matplotlib.pyplot as plot  # plotting
import pandas as pd  # data analysis
import pandas_datareader as pdr  # datareader
from scipy.stats import norm  # normal cdf

from ib_insync import *


class SpyDeltaHedge:
    """Class for pricing and hedging of SPX options

    Returns:
        obj: object with ib connection established and spx priced
    """

    def __init__(self, url="127.0.0.1", port=7497, client_id=2):
        """Initialize IB connection and create a contract for the underlying

        Args:
            url (str, optional): URL string for TWS or IB gateway. Defaults to "127.0.0.1"
            port (int, optional): Port number for TWS or IB gateway. Defaults to 4002
        """
        # ibkr connection
        self.ib = IB()
        self.ib.connect(url, port, clientId=client_id)

        # price the underlying security
        spx = Stock("VOO", "SMART", "USD")
        self.ib.qualifyContracts(spx)
        self.ib.reqMarketDataType(4)
        [ticker] = self.ib.reqTickers(spx)
        self.spx_price = ticker.marketPrice()

    def __del__(self):
        """Disconnects the IBKR session before object deletion"""
        self.ib.disconnect()

    def _get_option_contracts(self, rights=["C"]):
        """Fetch SPX options contracts"""
        opt_chain = self.ib.reqSecDefOptParams(
            self.spx.symbol, "", self.spx.secType, self.spx.conId
        )
        chain = next(
            c for c in opt_chain if c.tradingClass == "VOO" and c.exchange == "SMART"
        )

        # filtering lists
        strikes = [strike for strike in chain.strikes]
        expirations = sorted(exp for exp in chain.expirations)[:2]

        contracts = [
            Option("VOO", expiration, strike, right, "SMART", tradingClass="VOO")
            for right in rights
            for expiration in expirations
            for strike in strikes
        ]
        cons = self.ib.qualifyContracts(*contracts)
        return cons

    def sell_mispricing(self, num_contracts):
        """Sell contracts of the option with the largest mispricing

        Args:
            num_contracts (int): the number of contracts to sell
        """
        # get largest mispricing in option chain
        contracts = self._get_option_contracts()
        tickers = self.ib.reqTickers(*contracts)

        # contracts = [c for c in self._get_option_contracts]
        # order = MarketOrder("SELL", num_contracts)
        pass

    def _bs_price(S, K, T, r, sigma, opt="c"):
        """Price an option with the black-scholes model

        Args:
            S (float): Price of the underlying security
            K (float): Strike price
            T (float): time to maturity
            r (float): risk free interest rate
            sigma (float): volatility of the underlying security
            opt (str, optional): option type. Defaults to "C" (call)

        Returns:
            float: the black-scholes price of the option
        """
        d1 = (np.log(S / K) + (r + sigma**2 / 2.0) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        if opt == "c":
            bs_price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        elif opt == "p":
            bs_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        else:
            bs_price = None
        return bs_price

    def _bs_delta(S, K, T, r, sigma, opt="C"):
        """Calculate the black-scholes delta of the option

        Args:
            S (float): Price of the underlying security
            K (float): Strike price
            T (float): time to maturity
            r (float): risk free interest rate
            sigma (float): volatility of the underlying security
            opt (str, optional): option type. Defaults to "C" (call)

        Returns:
            float: the black-scholes delta of the option
        """
        d1 = (np.log(S / K) + (r + sigma**2 / 2.0) * T) / (sigma * np.sqrt(T))

        if opt == "C":
            bs_delta = norm.cdf(d1)
        elif opt == "P":
            bs_delta = -norm.cdf(-d1)
        else:
            bs_delta = None
        return bs_delta

    def _delta_hedge(self, sym):
        """Initiate a delta hedge for call options"""
        # get current positions
        positions = [p for p in self.ib.positions() if p.contract.symbol == sym]

        # ensure that you have an open option position
        opts = [p for p in positions if p.contract.secType == "OPT"]
        if not opts:
            print("No option position to hedge")
            return (None, None)
        option = opts[0]

        # use the delta to determine the optimal hedge
        # TODO:(BLACKSCHOLES IMPLEMENTATION)
        # delta = self._bs_delta(self.spx_price)
        delta = option.modelGreeks.delta
        delta_neutral_pos = -option.position * delta * 100

        # calculate the difference between the hedge requirement and the current position
        stks = [p for p in positions if p.contract.secType == "STK"]
        hedge = delta_neutral_pos - stks[0].position

        # return contract and order required to remain delta neutral
        contract = Stock("VOO", "SMART", "USD")
        order = MarketOrder("BUY", hedge)
        return (contract, order)

    def rebalance(self):
        """Rebalance portfolio to remain delta-neutral
        Runs daily
        """
        # get option positions
        options = [
            p.contract.symbol
            for p in self.ib.positions()
            if p.contract.secType == "OPT"
        ]

        # calculate the delta hedge trade needed to remain delta-neutral
        executions = []
        for opt in options:
            executions.append(self._delta_hedge(opt))

        # TODO:(EXECUTION VALIDATION) check whether the risk outweighs the transaction cost
        # dryrun = self.ib.whatIfOrder(contract, order)

        # execute the trades to remain delta-neutral
        for contract, order in executions:
            if contract and order:
                trade = self.ib.placeOrder(contract, order)
                assert order in self.ib.orders()
                assert trade in self.ib.trades()
                while not trade.isDone():
                    self.ib.waitOnUpdate()
